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
    CAMPAIGN_JSON_PATH = base_dir / "db" / "campaign.json"

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

    def save_campaign_json(state):
        with open(CAMPAIGN_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load_campaign_json():
        if CAMPAIGN_JSON_PATH.exists():
            with open(CAMPAIGN_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

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

    def get_example_adventure_descriptions():
        example_dirs = [base_dir / "example_adventures", base_dir / "example_campaigns"]
        adventure_files = []
        import glob
        for d in example_dirs:
            adventure_files.extend(glob.glob(str(d / "*.md")))
        adventures = []
        for file_path in adventure_files:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Use the first heading and the first long paragraph as the description
                lines = content.splitlines()
                title = next((l.strip('# ').strip() for l in lines if l.startswith('#') or l.lower().startswith('campaign:')), "Example Adventure")
                # Find the first paragraph after the title
                desc = ""
                for i, l in enumerate(lines):
                    if l.startswith('#') or l.lower().startswith('campaign:'):
                        # Find next non-empty, non-heading line
                        for l2 in lines[i+1:]:
                            if l2.strip() and not l2.startswith('#') and not l2.lower().startswith('campaign:'):
                                desc = l2.strip()
                                break
                        break
                adventures.append({"title": title, "description": desc, "full_text": content})
        return adventures

    async def start_new_campaign():
        # Use example adventures to inspire the campaign
        example_adventures = get_example_adventure_descriptions()
        if example_adventures:
            import random
            chosen = random.choice(example_adventures)
            prompt = f"Design a campaign inspired by the following adventure path. Use the setting, themes, and structure, but adapt as needed for a new group:\n\n{chosen['title']}\n\n{chosen['description']}\n\n{chosen['full_text']}\n\nGive the campaign a name and a 2-3 sentence overarching story. Then, outline 3-5 short adventure summaries (1-2 sentences each) that could make up the campaign. Format as: Adventure 1: <summary>\nAdventure 2: <summary>..."
        else:
            prompt = "Create a new D&D campaign. Give it a name and a 2-3 sentence overarching story. Then, outline 3-5 short adventure summaries (1-2 sentences each) that could make up the campaign. Format as: Adventure 1: <summary>\nAdventure 2: <summary>..."
        main_story = await get_llm_response(prompt, ollama_host, ollama_model)
        # Parse adventure summaries from the LLM response
        import re
        adventure_summaries = []
        for match in re.findall(r"Adventure \d+: (.+)", main_story):
            adventure_summaries.append(match.strip())
        # Set world_state to match the start of the campaign/adventure if possible
        starting_location = "Town Square"
        starting_description = world_state["description"]
        if adventure_summaries:
            # Try to extract a location from the first adventure summary
            import re
            first_summary = adventure_summaries[0]
            # Look for a location in the first sentence (before a colon or period)
            match = re.match(r"([^.\n:]+)[.:]", first_summary)
            if match:
                starting_location = match.group(1).strip()
            starting_description = first_summary.strip()
        campaign = {
            "name": main_story.split("\n")[0].strip(),
            "main_story": main_story.strip(),
            "adventures": [],
            "current_adventure": 0,
            "world_state": {
                "location": starting_location,
                "players": [],
                "description": starting_description,
                "image": None
            },
            "campaign_started": False
        }
        # Add adventure summaries to campaign and campaign.json
        adventures_json = []
        for summary in adventure_summaries:
            adventures_json.append({
                "name": "",
                "summary": summary,
                "description": summary
            })
        campaign_json = {
            "name": campaign["name"],
            "main_story": campaign["main_story"],
            "adventures": adventures_json,
            "current_adventure": 0,
            "campaign_started": False
        }
        save_campaign_json(campaign_json)
        # Only create the first adventure now, using its summary as the prompt
        if adventure_summaries:
            campaign["adventures"] = []
            campaign["current_adventure"] = 0
            first_adventure = await start_new_adventure(campaign)
            campaign["adventures"].append(first_adventure)
        save_campaign_state(campaign)
        return campaign

    async def start_new_adventure(campaign):
        campaign_json = load_campaign_json() or {}
        adv_idx = len(campaign["adventures"])
        # Use DM-provided description if available
        adventure_desc = ""
        if campaign_json.get("adventures") and adv_idx < len(campaign_json["adventures"]):
            adventure_desc = campaign_json["adventures"][adv_idx].get("description", "")
        if adventure_desc:
            prompt = f"Create the full adventure for '{campaign['name']}' - Adventure: '{adventure_desc}'. Use the DM's description as the basis."
        else:
            prompt = f"Create a new short adventure for the campaign '{campaign['name']}'. Give it a name and a 1-2 sentence summary."
        adv = await get_llm_response(prompt, ollama_host, ollama_model)
        adventure = {
            "name": adv.split("\n")[0].strip(),
            "summary": adv.strip(),
            "completed": False
        }
        campaign["adventures"].append(adventure)
        campaign["current_adventure"] = len(campaign["adventures"]) - 1
        campaign["world_state"] = world_state.copy()
        save_campaign_state(campaign)
        # Also update campaign.json with adventure summary if not present
        if campaign_json.get("adventures") and adv_idx < len(campaign_json["adventures"]):
            campaign_json["adventures"][adv_idx]["name"] = adventure["name"]
            campaign_json["adventures"][adv_idx]["summary"] = adventure["summary"]
        else:
            adventures_json = campaign_json.get("adventures", [])
            adventures_json.append({
                "name": adventure["name"],
                "summary": adventure["summary"],
                "description": adventure["summary"]
            })
            campaign_json["adventures"] = adventures_json
        campaign_json["current_adventure"] = campaign["current_adventure"]
        campaign_json["campaign_started"] = campaign.get("campaign_started", False)
        save_campaign_json(campaign_json)
        return adventure

    def run_sync(awaitable):
        import asyncio
        try:
            return asyncio.get_event_loop().run_until_complete(awaitable)
        except RuntimeError:
            return asyncio.new_event_loop().run_until_complete(awaitable)

    async def session_zero(channel):
        await channel.send("Game State: Session Zero\nWelcome to Session Zero! Let's create your characters. Each player, please say anything in chat to begin your character creation journey.")

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
            user_mention = get_user_mention(user, None)
            if user_mention not in world_state["players"]:
                world_state["players"].append(user_mention)
            campaign["world_state"] = world_state.copy()
            save_campaign_state(campaign)
        await dm.send(f"Character creation complete! Welcome, {name} the {race_class}.")
        # Announce in main channel
        if discord_channel:
            channel = bot.get_channel(int(discord_channel))
            if channel:
                await channel.send(f"{user.display_name} has created a character! Game State: Session Zero.")

    # --- State Machine States ---
    # 'pre_session_zero' - No campaign exists
    # 'session_zero' - Campaign exists, character creation phase
    # 'campaign_started' - Campaign started, no adventure running
    # 'adventure_running' - An adventure is active

    def get_campaign_state():
        campaign = load_campaign_state()
        if not campaign:
            return 'pre_session_zero'
        if not campaign.get('campaign_started'):
            return 'session_zero'
        adventures = campaign.get('adventures', [])
        adv_idx = campaign.get('current_adventure', 0)
        if campaign.get('campaign_started') and adv_idx < len(adventures) and not adventures[adv_idx].get('completed', False):
            return 'adventure_running'
        return 'campaign_started'

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        if discord_channel:
            state = get_campaign_state()
            if state == 'pre_session_zero':
                campaign = await start_new_campaign()
                save_campaign_state(campaign)
                # Also update campaign.json
                campaign_json = {
                    "name": campaign["name"],
                    "main_story": campaign["main_story"],
                    "adventures": [],
                    "current_adventure": 0,
                    "campaign_started": False,
                    "state": "session_zero"
                }
                save_campaign_json(campaign_json)
            channel = bot.get_channel(int(discord_channel))
            if state == 'pre_session_zero' or state == 'session_zero':
                await session_zero(channel)
            # Do not auto-start campaign or adventure here

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return
        if discord_channel and str(message.channel.id) != discord_channel:
            return
        state = get_campaign_state()
        # Only allow character creation during session_zero
        if isinstance(message.channel, discord.DMChannel):
            if state == 'pre_session_zero':
                await message.channel.send("The campaign setup is not complete yet. Please wait for the DM to begin Session Zero and character creation.")
                return
            if state == 'session_zero':
                # Allow any player who has created a character to ask questions by mentioning the bot
                content = message.content.strip()
                bot_mention = bot.user.mention if bot.user else None
                mentioned = False
                if bot_mention and bot_mention in content:
                    mentioned = True
                elif bot.user and bot.user.name.lower() in content.lower():
                    mentioned = True
                if user_id not in characters:
                    await guide_character_creation(message.author)
                    return
                if content.startswith('!'):
                    await handle_command(message, content)
                elif mentioned:
                    await handle_session_zero_question(message)
                else:
                    # Remain silent, let players chat among themselves
                    pass
                return
        user_id = str(message.author.id)
        if state == 'pre_session_zero':
            await message.channel.send("The campaign setup is not complete yet. Please wait for the DM to begin Session Zero and character creation.")
            return
        if state == 'session_zero':
            if user_id not in characters:
                await guide_character_creation(message.author)
                return
            content = message.content.strip()
            # Only answer if the bot is mentioned
            bot_mention = bot.user.mention if bot.user else None
            mentioned = False
            if bot_mention and bot_mention in content:
                mentioned = True
            elif bot.user and bot.user.name.lower() in content.lower():
                mentioned = True
            if content.startswith('!'):
                await handle_command(message, content)
            elif mentioned:
                await handle_session_zero_question(message)
            else:
                # Remain silent, let players chat among themselves
                pass
            return
        if state == 'campaign_started':
            content = message.content.strip()
            if content.startswith('!'):
                await handle_command(message, content)
            else:
                await handle_campaign_started_message(message)
            return
        if state == 'adventure_running':
            content = message.content.strip()
            if content.startswith('!'):
                await handle_command(message, content)
            else:
                await handle_player_message(message)
            return
        # If unknown state, ignore all messages

    async def handle_campaign_started_message(message):
        """Handle player messages during campaign_started (shopping, downtime, pre-adventure)."""
        campaign = load_campaign_state()
        if not campaign:
            await message.channel.send("No campaign info available yet.")
            return
        context = campaign.get("main_story", "")
        prompt = (
            "You are the DM. The campaign has started, but no adventure is running yet. "
            "Players may shop, explore the town, interact with NPCs, or prepare for the adventure. "
            "Answer as the DM, roleplaying shopkeepers, describing shops, prices, and available items, or responding to downtime activities. "
            "Do NOT start the adventure or narrate story events.\n\n"
            f"Campaign Info:\n{context}\n\nPlayer Message:\n{message.content.strip()}"
        )
        response = await get_llm_response(prompt, ollama_host, ollama_model)
        await message.channel.send(response)

    async def handle_command(message, content):
        state = get_campaign_state()
        parts = content[1:].split()
        command = parts[0].lower() if parts else ''
        args = parts[1:]
        if command == 'startcampaign':
            if state != 'session_zero':
                await message.channel.send("You can only start the campaign after Session Zero (character creation phase).")
                return
            campaign = load_campaign_state()
            if not campaign:
                await message.channel.send("No campaign exists. Please ask all players to create their characters first.")
                return
            if campaign.get('campaign_started'):
                await message.channel.send("Campaign has already started!")
                return
            # Mark campaign as started
            campaign['campaign_started'] = True
            campaign['state'] = 'campaign_started'
            save_campaign_state(campaign)
            await message.channel.send("Campaign is starting!")
            await send_initial_world_state()
            return
        if command == 'startadventure':
            if state != 'campaign_started':
                await message.channel.send("You can only start a new adventure after the campaign has started and no adventure is running.")
                return
            campaign = load_campaign_state()
            adv_idx = campaign.get('current_adventure', 0)
            if adv_idx < len(campaign.get('adventures', [])) and not campaign['adventures'][adv_idx].get('completed', False):
                await message.channel.send("Current adventure is still ongoing!")
                return
            # Start a new adventure
            adventure = await start_new_adventure(campaign)
            campaign['state'] = 'adventure_running'
            save_campaign_state(campaign)
            await message.channel.send(f"**New Adventure!**\n{adventure['name']}\n{adventure['summary']}")
            await send_initial_world_state()
            return
        if state != 'adventure_running' and command not in ['help', 'players']:
            await message.channel.send("You can only use this command during an active adventure.")
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
            # Send long messages in chunks of 2000 characters or less
            max_len = 2000
            for i in range(0, len(msg), max_len):
                await channel.send(msg[i:i+max_len])
        world_msg = f"**Current Location:** {world_state['location']}\n\n{world_state['description']}"
        image_path = world_state.get("image")
        if not image_path:
            # Generate image if missing using ensure_world_image (only pass required args)
            image_path = await ensure_world_image(world_state["location"], world_state["description"])
            world_state["image"] = image_path
        print(f"[DEBUG] image_path: {image_path}, exists: {Path(image_path).exists() if image_path else 'N/A'}")
        if image_path and Path(image_path).exists():
            print(f"[DEBUG] Sending image to Discord: {image_path}")
            embed = discord.Embed(description=world_msg)
            file = File(image_path, Path(image_path).name)
            embed.set_image(url=f"attachment://{Path(image_path).name}")
            await channel.send(embed=embed, file=file)
        else:
            print(f"[DEBUG] No image to send. image_path: {image_path}")
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
            # Remove any existing Exits line from the LLM response
            import re
            server_message = re.sub(r"\n?Exits:.*", "", server_message, flags=re.IGNORECASE).rstrip()
            # Always append Exits line to the message
            exits_line = f"Exits: {', '.join(exits) if exits else 'None'}"
            server_message = server_message + f"\n\n{exits_line}"
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

    async def handle_session_zero_question(message):
        """Answer player questions about the campaign/rules during session_zero after character creation."""
        campaign = load_campaign_state()
        if not campaign:
            await message.channel.send("No campaign info available yet.")
            return
        context = campaign.get("main_story", "")
        import re
        context_clean = re.sub(r"^.*Exits:.*$", "", context, flags=re.MULTILINE).strip()
        prompt = (
            "You are the DM. Answer the player's question as a helpful guide about the campaign world, setting, or rules. "
            "Do NOT narrate the current in-game situation, location, or events. Only provide information about the world, lore, rules, or character options. "
            "If the question is about the story so far, say that the adventure hasn't started yet.\n\n"
            f"Campaign Info:\n{context_clean}\n\nPlayer Question:\n{message.content.strip()}"
        )
        async with message.channel.typing():
            response = await get_llm_response(prompt, ollama_host, ollama_model)
            response_clean = re.sub(r"^.*Exits:.*$", "", response, flags=re.MULTILINE).strip()
            await message.channel.send(response_clean)

    # Ensure DB files exist, create if missing
    if not CAMPAIGN_STATE_PATH.exists():
        # Create a new campaign and save to file
        import asyncio
        campaign = asyncio.get_event_loop().run_until_complete(start_new_campaign())
        save_campaign_state(campaign)
    if not CHARACTERS_PATH.exists():
        with open(CHARACTERS_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
    if not CAMPAIGN_JSON_PATH.exists():
        campaign = load_campaign_state()
        if campaign:
            campaign_json = {
                "name": campaign["name"],
                "main_story": campaign["main_story"],
                "adventures": [
                    {
                        "name": adv.get("name", ""),
                        "summary": adv.get("summary", ""),
                        "description": adv.get("summary", "")
                    } for adv in campaign.get("adventures", [])
                ],
                "current_adventure": campaign.get("current_adventure", 0),
                "campaign_started": campaign.get("campaign_started", False)
            }
            save_campaign_json(campaign_json)

    # At the end of init_bot, start the bot and block the main thread
    bot.run(discord_token)