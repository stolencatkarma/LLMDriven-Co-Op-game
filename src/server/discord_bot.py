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
            "current_adventure": 0
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
        await dm.send(f"Character creation complete! Welcome, {name} the {race_class}.")

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        if discord_channel:
            campaign = load_campaign_state()
            if not campaign:
                channel = bot.get_channel(int(discord_channel))
                await session_zero(channel)
            else:
                await send_initial_world_state()

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

    async def handle_command(message, content):
        parts = content[1:].split()
        command = parts[0].lower() if parts else ''
        args = parts[1:]
        if command == 'roll':
            import random
            result = random.randint(1, 20)
            await message.channel.send(f"🎲 {message.author.display_name} rolled a d20: **{result}**")
        elif command == 'move':
            if not args:
                await message.channel.send("Usage: !move <destination>")
                return
            destination = ' '.join(args)
            await handle_movement(message, destination, world_state["location"], via_command=True)
        elif command == 'equip':
            if not args:
                await message.channel.send("Usage: !equip <item or phrase>")
                return
            item_phrase = ' '.join(args)
            user_id = str(message.author.id)
            char = characters.get(user_id)
            if not char:
                await message.channel.send("Character not found.")
                return
            from llm_utils import llm_can_equip
            # Call LLM to adjudicate equip request
            equip_result = await llm_can_equip(char, item_phrase, ollama_host, ollama_model)
            if equip_result.get('allowed'):
                slot = equip_result.get('slot') or 'Misc'
                try:
                    char.equip_item(item_phrase, slot)
                    save_characters(characters)
                    await message.channel.send(f"{message.author.display_name} equipped {item_phrase} in {slot} slot.")
                except Exception as e:
                    await message.channel.send(f"Could not equip: {e}")
            else:
                await message.channel.send(f"Cannot equip '{item_phrase}': {equip_result.get('reason','Not allowed.')}")
        elif command == 'equipment':
            user_id = str(message.author.id)
            char = characters.get(user_id)
            if not char:
                await message.channel.send("Character not found.")
                return
            equipped = char.list_equipped()
            inventory = char.list_inventory()
            eq_lines = [f"**Equipped Items:**"]
            if equipped:
                for slot, item in equipped.items():
                    eq_lines.append(f"- {slot}: {item}")
            else:
                eq_lines.append("(None equipped)")
            eq_lines.append("\n**Inventory:**")
            if inventory:
                for item in inventory:
                    eq_lines.append(f"- {item}{' (equipped)' if char.is_equipped(item) else ''}")
            else:
                eq_lines.append("(Empty)")
            await message.channel.send("\n".join(eq_lines))
        elif command == 'players':
            # List all active players (those with characters)
            if not characters:
                await message.channel.send("No active players yet.")
                return
            player_lines = ["**Active Players:**"]
            for user_id, char in characters.items():
                name = char.get('name') or getattr(char, 'name', None) or f"User {user_id}"
                race_class = char.get('race_class') or f"{getattr(char, 'race', '')} {getattr(char, 'char_class', '')}".strip()
                player_lines.append(f"- {name} ({race_class})")
            await message.channel.send("\n".join(player_lines))
        else:
            await message.channel.send(f"Unknown command: {command}")

    async def send_initial_world_state():
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

    async def handle_player_message(message):
        player = str(message.author)
        content = message.content.strip()
        
        if player not in world_state["players"]:
            world_state["players"].append(player)
        
        chat_history.append({"sender": player, "message": content})
        await process_player_action(message, content)

    async def process_player_action(message, content: str):
        prev_location = world_state["location"]
        new_location = detect_movement(content, prev_location)
        if new_location:
            # Instead of calling handle_movement directly, call the !move command as if the player did
            fake_command = f"!move {new_location}"
            await handle_command(message, fake_command)
        else:
            await generate_dm_response(message, content, prev_location)

    def detect_movement(content: str, current_location: str) -> Optional[str]:
        current_room = get_room(current_location)
        exits = current_room.get("exits", []) if current_room else []
        
        # Check exact exit matches first
        for exit_name in exits:
            if exit_name.lower() in content.lower():
                return exit_name
        
        # Fallback to regex pattern
        match = re.search(r"\bgo (\w+)\b", content.lower())
        return match.group(1).capitalize() if match else None

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
            update_world_state_from_room(next_room)
        await send_room_update(message.channel)

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
        set_room(new_location, {
            "description": server_message,
            "image": image_path,
            "exits": exits,
            "previous": prev_location
        })
        # Ensure two-way connection in previous room
        if prev_room:
            prev_exits = prev_room.get("exits", [])
            if new_location not in prev_exits:
                prev_exits.append(new_location)
                prev_room["exits"] = prev_exits
                set_room(prev_location, prev_room)
        world_state.update({
            "description": server_message,
            "image": image_path
        })

    def update_world_state_from_room(room_data: dict):
        world_state["description"] = room_data.get("description", world_state["description"])
        world_state["image"] = room_data.get("image")

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
            await send_dm_response(message.channel, server_message, exits)

    async def send_dm_response(channel, raw_message: str, exits: list):
        clean_message = re.sub(r"", "", raw_message, flags=re.DOTALL).strip()
        reply = f"**DM:** {replace_mentions(clean_message, channel)}"
        if exits:
            reply += f"\n\n**Exits:** {', '.join(exits)}"
        else:
            reply += "\n\n**Exits:** None"
        image_path = world_state.get("image")
        if image_path and Path(image_path).exists():
            with open(image_path, "rb") as img_fp:
                await channel.send(file=File(img_fp, Path(image_path).name))
        await channel.send(reply)

    def replace_mentions(text: str, channel) -> str:
        if not hasattr(channel, "guild"):
            return text
        return re.sub(
            r"@(\d{17,20})",
            lambda m: get_user_mention(m.group(1), channel.guild),
            text
        )

    def get_user_mention(user_id: str, guild) -> str:
        user = guild.get_member(int(user_id))
        return f"@{user.display_name}" if user else f"@{user_id}"

    # Start the bot
    if discord_token:
        bot.run(discord_token)