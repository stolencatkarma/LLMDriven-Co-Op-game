import os
import re
import discord
from discord import File
from typing import Optional
from pathlib import Path
from llm_utils import get_llm_response
from game_state import save_game_state, load_game_state
from room_utils import get_room, set_room, extract_exits_from_dm
from image_utils import ensure_world_image
import importlib
from utils.discord_utils import replace_mentions, get_user_mention
from utils.message_utils import send_dm_response
from utils.movement_utils import detect_movement
from utils.world_utils import update_world_state_from_room

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)

def init_bot(
    discord_token: str,
    discord_channel: Optional[str],
    base_dir: Path,
    ollama_host: str,
    ollama_model: str
):
    import json
    CAMPAIGN_STATE_PATH = base_dir / "db" / "campaign_state.json"
    CHARACTERS_PATH = base_dir / "db" / "characters.json"

    def save_campaign_state(state):
        with open(CAMPAIGN_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load_campaign_state():
        if CAMPAIGN_STATE_PATH.exists():
            with open(CAMPAIGN_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def load_characters():
        if CHARACTERS_PATH.exists():
            with open(CHARACTERS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_characters(characters):
        with open(CHARACTERS_PATH, "w", encoding="utf-8") as f:
            json.dump(characters, f, indent=2)

    global world_state, chat_history
    campaign = load_campaign_state()
    if campaign and "world_state" in campaign:
        world_state = campaign["world_state"]
    else:
        world_state = {
            "location": "Town Square",
            "players": [],
            "description": "🌳 **Town Square** 🌳\n\nYou are in the bustling town square.\nAdventurers gather here, and the fountain sparkles in the sunlight.",
            "image": None
        }
    chat_history = []
    
    # Load initial game state
    saved_location = load_game_state(base_dir)
    if saved_location:
        starting_room = get_room(saved_location)
        if starting_room:
            world_state.update({
                "location": saved_location,
                "description": starting_room.get("description", world_state["description"]),
                "image": starting_room.get("image")
            })

    characters = load_characters()

    async def start_new_campaign():
        prompt = "Create a new D&D campaign. Give it a name and a 2-3 sentence overarching story."
        main_story = await get_llm_response(prompt, ollama_host, ollama_model)
        campaign = {
            "name": main_story.split("\n")[0].strip(),
            "main_story": main_story.strip(),
            "adventures": [],
            "current_adventure": 0,
            "world_state": world_state.copy()  # Save initial world state
        }
        save_campaign_state(campaign)
        return campaign

    async def start_new_adventure(campaign):
        prompt = f"Create a new short adventure for the campaign '{campaign['name']}'. Give it a name and a 1-2 sentence summary."
        adv = await get_llm_response(prompt, ollama_host, ollama_model)
        adventure = {
            "name": adv.split("\n")[0].strip(),
            "summary": adv.strip(),
            "completed": False
        }
        campaign["adventures"].append(adventure)
        campaign["current_adventure"] = len(campaign["adventures"]) - 1
        campaign["world_state"] = world_state.copy()  # Save world state at adventure start
        save_campaign_state(campaign)
        return adventure

    def run_sync(awaitable):
        import asyncio
        try:
            return asyncio.get_event_loop().run_until_complete(awaitable)
        except RuntimeError:
            return asyncio.new_event_loop().run_until_complete(awaitable)

    async def session_zero(channel):
        await channel.send("Welcome to Session Zero! Let's create your characters. Each player, please say anything in chat to begin your character creation journey.")

    async def guide_character_creation(user):
        dm = await user.create_dm()
        
        # World/setting intro for the player
        await dm.send("""
Welcome to the campaign! All adventures take place in and around a sprawling Mega City and its surrounding wasteland. The Mega City is a towering, neon-lit metropolis filled with advanced technology, cybernetic enhancements, powerful corporations, and a stark divide between rich and poor. Outside the city lies a dangerous wasteland of ruins, mutants, and lawless zones. Magic is rare or replaced by psionics and advanced science. Please create a character that fits this setting (e.g., cybernetics, hacking, futuristic weapons, etc).
""")
        await dm.send("Let's create your character! What is your character's name?")
        def check(m):
            return m.author == user and isinstance(m.channel, discord.DMChannel)
        name_msg = await bot.wait_for('message', check=check)
        name = name_msg.content.strip()
        await dm.send(f"Great! What is {name}'s race and class?")
        rc_msg = await bot.wait_for('message', check=check)
        race_class = rc_msg.content.strip()
        await dm.send(f"Awesome! Give me a one-sentence backstory for {name}.")
        backstory_msg = await bot.wait_for('message', check=check)
        backstory = backstory_msg.content.strip()
        char_data = {"name": name, "race_class": race_class, "backstory": backstory}
        characters[str(user.id)] = char_data
        save_characters(characters)
        # --- AUTO-SAVE CAMPAIGN STATE (character join) ---
        campaign = load_campaign_state()
        if campaign:
            if "players" not in world_state:
                world_state["players"] = []
            user_mention = get_user_mention(user)
            if user_mention not in world_state["players"]:
                world_state["players"].append(user_mention)
            campaign["world_state"] = world_state.copy()
            save_campaign_state(campaign)
        await dm.send(f"Character creation complete! Welcome, {name} the {race_class}.")

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        if discord_channel:
            campaign = load_campaign_state()
            if not campaign:
                channel = bot.get_channel(int(discord_channel))
                await session_zero(channel)
            # Do not auto-start campaign or adventure here
            # else:
            #     await send_initial_world_state()

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return
        if discord_channel and str(message.channel.id) != discord_channel:
            return
        # Character creation for new users
        if isinstance(message.channel, discord.DMChannel):
            # Already handled in guide_character_creation
            return
        user_id = str(message.author.id)
        if user_id not in characters:
            await guide_character_creation(message.author)
            return
        content = message.content.strip()
        if content.startswith('!'):
            await handle_command(message, content)
        else:
            await handle_player_message(message)

    command_map = {
        'roll': ('commands.roll', 'roll_command'),
        'move': ('commands.move', 'move_command'),
        'equip': ('commands.equip', 'equip_command'),
        'equipment': ('commands.equipment', 'equipment_command'),
        'players': ('commands.players', 'players_command'),
        'buy': ('commands.buy', 'buy_command'),
        'sell': ('commands.sell', 'sell_command'),
        'shop': ('commands.shop', 'shop_command'),
        'help': ('commands.help', 'help_command'),
        # New campaign/adventure commands
        'startcampaign': (None, None),
        'startadventure': (None, None),
    }
    
    async def handle_command(message, content):
        parts = content[1:].split()
        command = parts[0].lower() if parts else ''
        args = parts[1:]
        if command == 'startcampaign':
            campaign = load_campaign_state()
            if not campaign:
                await message.channel.send("No campaign exists. Please ask all players to create their characters first.")
                return
            if campaign.get('campaign_started'):
                await message.channel.send("Campaign has already started!")
                return
            # Mark campaign as started
            campaign['campaign_started'] = True
            save_campaign_state(campaign)
            await message.channel.send("Campaign is starting!")
            await send_initial_world_state()
            return
        if command == 'startadventure':
            campaign = load_campaign_state()
            if not campaign or not campaign.get('campaign_started'):
                await message.channel.send("No campaign is running. Use !startcampaign first.")
                return
            adv_idx = campaign.get('current_adventure', 0)
            if adv_idx < len(campaign.get('adventures', [])) and not campaign['adventures'][adv_idx].get('completed', False):
                await message.channel.send("Current adventure is still ongoing!")
                return
            # Start a new adventure
            adventure = await start_new_adventure(campaign)
            await message.channel.send(f"**New Adventure!**\n{adventure['name']}\n{adventure['summary']}")
            await send_initial_world_state()
            return
        if command in command_map and command_map[command][0]:
            module_name, func_name = command_map[command]
            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name)
            kwargs = {
                'characters': characters,
                'save_characters': save_characters,
                'ollama_host': ollama_host,
                'ollama_model': ollama_model,
                'handle_movement': handle_movement,
                'world_state': world_state
            }
            await func(message, args, **kwargs)
            # --- AUTO-SAVE CAMPAIGN STATE after any command ---
            campaign = load_campaign_state()
            if campaign:
                campaign["world_state"] = world_state.copy()
                save_campaign_state(campaign)
        else:
            await message.channel.send(f"Unknown command: {command}")

    async def send_initial_world_state():
        # Only show world state if campaign has started
        campaign = load_campaign_state()
        if not campaign or not campaign.get('campaign_started'):
            return
        # Load or create campaign/adventure
        campaign = load_campaign_state()
        if not campaign:
            campaign = await start_new_campaign()
            adventure = await start_new_adventure(campaign)
            msg = f"**New Campaign Started!**\n{campaign['main_story']}\n\n**First Adventure:** {adventure['name']}\n{adventure['summary']}"
        else:
            adv_idx = campaign.get("current_adventure", 0)
            if adv_idx >= len(campaign["adventures"]):
                adventure = await start_new_adventure(campaign)
                msg = f"**New Adventure!**\n{adventure['name']}\n{adventure['summary']}"
            else:
                adventure = campaign["adventures"][adv_idx]
                msg = f"**Resuming Adventure:** {adventure['name']}\n{adventure['summary']}"
        channel = bot.get_channel(int(discord_channel))
        if channel:
            await channel.send(msg)
        world_msg = f"**Current Location:** {world_state['location']}\n\n{world_state['description']}"
        image_path = world_state.get("image")
        if not image_path:
            # Generate image if missing using ensure_world_image (only pass required args)
            image_path = await ensure_world_image(world_state["location"], world_state["description"])
            world_state["image"] = image_path
        print(f"[DEBUG] image_path: {image_path}, exists: {Path(image_path).exists() if image_path else 'N/A'}")
        if image_path and Path(image_path).exists():
            with open(image_path, "rb") as img_fp:
                await channel.send(world_msg, file=File(img_fp, Path(image_path).name))
        else:
            await channel.send(world_msg)
        # --- AUTO-SAVE CAMPAIGN STATE after world state update ---
        campaign = load_campaign_state()
        if campaign:
            campaign["world_state"] = world_state.copy()
            save_campaign_state(campaign)

    async def handle_player_message(message):
        player = str(message.author)
        content = message.content.strip()
        
        if player not in world_state["players"]:
            world_state["players"].append(player)
            # --- AUTO-SAVE CAMPAIGN STATE ---
            campaign = load_campaign_state()
            if campaign:
                campaign["world_state"] = world_state.copy()
                save_campaign_state(campaign)
        
        chat_history.append({"sender": player, "message": content})
        await process_player_action(message, content)

    async def process_player_action(message, content: str):
        prev_location = world_state["location"]
        new_location = detect_movement(content, prev_location, get_room)
        if new_location:
            # Instead of calling handle_movement directly, call the !move command as if the player did
            fake_command = f"!move {new_location}"
            await handle_command(message, fake_command)
        else:
            await generate_dm_response(message, content, prev_location)

    async def handle_movement(message, new_location: str, prev_location: str, via_command=False):
        if not via_command:
            await message.channel.send("All movement must use the !move command.")
            return
        world_state["location"] = new_location
        save_game_state(base_dir, new_location)
        next_room = get_room(new_location)
        if not next_room:
            await create_new_room(message, new_location, prev_location)
        else:
            # Ensure two-way connection
            prev_room = get_room(prev_location)
            if prev_room:
                exits = prev_room.get("exits", [])
                if new_location not in exits:
                    exits.append(new_location)
                    prev_room["exits"] = exits
                    set_room(prev_location, prev_room)
            update_world_state_from_room(world_state, next_room)
        await send_room_update(message.channel)
        # --- AUTO-SAVE CAMPAIGN STATE ---
        campaign = load_campaign_state()
        if campaign:
            campaign["world_state"] = world_state.copy()
            save_campaign_state(campaign)

    async def create_new_room(message, new_location: str, prev_location: str):
        prev_room = get_room(prev_location)
        # Prompt LLM to generate a room with at least one exit, including the previous room
        llm_prompt = (
            f"Describe the new room '{new_location}' that connects to '{prev_location}'. "
            f"The room must have at least one exit, and one exit must be '{prev_location}'. "
            f"List all exits at the end in the format: Exits: ..."
        )
        server_message = await get_llm_response(llm_prompt, ollama_host, ollama_model)
        exits = extract_exits_from_dm(server_message)
        # Guarantee at least one exit (the previous room)
        if prev_location not in exits:
            exits.append(prev_location)
        if not exits:
            exits = [prev_location]
        image_path = await ensure_world_image(new_location, server_message)
        # Build named exits: use LLM to suggest names, fallback to generic if needed
        named_exits = {}
        for exit_name in exits:
            if exit_name.lower() == prev_location.lower():
                named_exits["back"] = prev_location
            else:
                # Use the exit name as the direction if possible
                named_exits[exit_name.lower()] = exit_name
        set_room(new_location, {
            "description": server_message,
            "image": image_path,
            "exits": named_exits,
            "previous": prev_location
        })
        # Ensure two-way connection in previous room
        if prev_room:
            prev_exits = prev_room.get("exits", {})
            if isinstance(prev_exits, list):
                prev_exits = {e: new_location for e in prev_exits if e != new_location}
            if new_location not in prev_exits.values():
                prev_exits["forward"] = new_location
                prev_room["exits"] = prev_exits
                set_room(prev_location, prev_room)
        world_state.update({
            "description": server_message,
            "image": image_path
        })
        # --- AUTO-SAVE CAMPAIGN STATE ---
        campaign = load_campaign_state()
        if campaign:
            campaign["world_state"] = world_state.copy()
            save_campaign_state(campaign)

    async def generate_dm_response(message, content: str, prev_location: str):
        async with message.channel.typing():
            server_message = await get_llm_response(content, ollama_host, ollama_model)
            room_data = get_room(world_state["location"]) or {}
            exits = extract_exits_from_dm(server_message)
            # Always append Exits line to the message
            exits_line = f"Exits: {', '.join(exits) if exits else 'None'}"
            if not server_message.strip().endswith(exits_line):
                server_message = server_message.rstrip() + f"\n\n{exits_line}"
            chat_history.append({"sender": "DM", "message": server_message})
            if exits:
                room_data["exits"] = exits
                set_room(world_state["location"], room_data)
            await send_dm_response(message.channel, server_message, exits, world_state, lambda t, c: replace_mentions(t, c, get_user_mention))
            # --- AUTO-SAVE CAMPAIGN STATE ---
            campaign = load_campaign_state()
            if campaign:
                campaign["world_state"] = world_state.copy()
                save_campaign_state(campaign)

    # At the end of init_bot, start the bot and block the main thread
    bot.run(discord_token)