import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import httpx
import discord
import signal
import sys
import threading
from room_utils import set_rooms_db_path
import re  # <-- Add this line

# Load environment variables from .env file
load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:latest")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL = os.getenv("DISCORD_CHANNEL")  # Optional: restrict to a channel ID

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "db" / "worldImages.json"

# --- Set the path for rooms_db.json ---
set_rooms_db_path(BASE_DIR / "db" / "rooms.json")

# In-memory state
chat_history = []
world_state = {
    "location": "Town Square",
    "players": [],
    "description": "🌳 **Town Square** 🌳\n\nYou are in the bustling town square.\nAdventurers gather here, and the fountain sparkles in the sunlight.",
    "image": None
}

# Load world images
if DB_PATH.exists():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        world_images = json.load(f)
else:
    world_images = {}

ROOMS_DB_PATH = BASE_DIR / "db" / "rooms.json"
if ROOMS_DB_PATH.exists():
    with open(ROOMS_DB_PATH, "r", encoding="utf-8") as f:
        rooms_db = json.load(f)
else:
    rooms_db = {}

# --- Add import for room_utils ---
from room_utils import (
    get_room_key, get_room, set_room, save_rooms_db, extract_exits_from_dm
)

GAME_STATE_PATH = BASE_DIR / "db" / "game_state.json"

def save_game_state():
    GAME_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GAME_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"location": world_state["location"]}, f)

def load_game_state():
    if GAME_STATE_PATH.exists():
        with open(GAME_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("location")
    return None

# --- Initialize world_state from persistent game_state if available ---
saved_location = load_game_state()
if saved_location and get_room(saved_location):
    starting_room = get_room(saved_location)
    world_state = {
        "location": saved_location,
        "players": [],
        "description": starting_room.get("description", "🌳 **Town Square** 🌳\n\nYou are in the bustling town square.\nAdventurers gather here, and the fountain sparkles in the sunlight."),
        "image": starting_room.get("image")
    }
else:
    world_state = {
        "location": "Town Square",
        "players": [],
        "description": "🌳 **Town Square** 🌳\n\nYou are in the bustling town square.\nAdventurers gather here, and the fountain sparkles in the sunlight.",
        "image": None
    }

# In-memory state
chat_history = []
world_state = {
    "location": "Town Square",
    "players": [],
    "description": "🌳 **Town Square** 🌳\n\nYou are in the bustling town square.\nAdventurers gather here, and the fountain sparkles in the sunlight.",
    "image": None
}

# Load world images
if DB_PATH.exists():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        world_images = json.load(f)
else:
    world_images = {}

ROOMS_DB_PATH = BASE_DIR / "db" / "rooms.json"
if ROOMS_DB_PATH.exists():
    with open(ROOMS_DB_PATH, "r", encoding="utf-8") as f:
        rooms_db = json.load(f)
else:
    rooms_db = {}

def save_rooms_db():
    ROOMS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ROOMS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(rooms_db, f, indent=2)

async def ensure_world_image(location, description):
    images_dir = BASE_DIR / "db" / "worldImages"
    print(f"[DEBUG] ensure_world_image called for location: {location}")
    if location in world_images:
        file_path = images_dir / world_images[location]
        print(f"[DEBUG] Checking existing image at: {file_path}")
        if file_path.exists():
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    img.verify()
                print(f"[DEBUG] Existing image is valid: {file_path}")
                return str(file_path)
            except Exception as e:
                print(f"[DEBUG] Invalid or corrupted image found for {location}, regenerating... Exception: {e}")
                file_path.unlink(missing_ok=True)
    prompt = f"A beautiful, detailed illustration of: {description.replace('**', '')}"
    print(f"[DEBUG] Sending image generation request to SD WebUI for prompt: {prompt}")
    try:
        async with httpx.AsyncClient() as client:
            payload = {"prompt": prompt}
            # Try both common endpoints for SD WebUI
            endpoints = [
                "http://localhost:7860/sdapi/v1/txt2img",
                "http://127.0.0.1:7860/sdapi/v1/txt2img",
                "http://localhost:7860/sdapi/v1/txt2img/",
                "http://127.0.0.1:7860/sdapi/v1/txt2img/"
            ]
            for endpoint in endpoints:
                print(f"[DEBUG] Trying SD WebUI endpoint: {endpoint}")
                try:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        timeout=120
                    )
                except Exception as e:
                    print(f"[Bot] Exception connecting to {endpoint}: {e}")
                    continue
                print(f"[DEBUG] SD WebUI response status: {response.status_code}")
                print(f"[DEBUG] SD WebUI response text: {response.text[:500]!r}")
                if response.status_code == 200:
                    data = response.json()
                    images = data.get("images")
                    if not images or not images[0]:
                        print("[Bot] SD WebUI did not return an image.")
                        return None
                    import base64
                    filename = f"{location.replace(' ', '_').lower()}.png"
                    file_path = images_dir / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "wb") as f:
                        f.write(base64.b64decode(images[0]))
                    from PIL import Image
                    with Image.open(file_path) as img:
                        img.verify()
                    world_images[location] = filename
                    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(DB_PATH, "w", encoding="utf-8") as f:
                        json.dump(world_images, f, indent=2)
                    print(f"[DEBUG] Image saved and verified at: {file_path}")
                    return str(file_path)
                else:
                    print(f"[Bot] SD WebUI endpoint {endpoint} failed: {response.status_code} {response.text}")
            print("[Bot] All SD WebUI endpoints failed. Is the server running? Is the API enabled?")
            print("[Bot] TIP: If you see 404 errors, make sure the API is enabled in SD WebUI (check 'Settings > User interface > Show API' and restart).")
            return None
    except Exception as e:
        print("[Bot] SD WebUI image generation failed:", e)
    return None

# Add a global LLM system prompt (customize as needed)
LLM_SYSTEM_PROMPT = """
You are a highly intelligent, experienced, and creative Dungeon Master for a D20-based tabletop role-playing game.
Your goal is to create an engaging, immersive, and memorable experience for the players. You will be responsible
for managing the game world, creating encounters, adjudicating rules, and telling stories that captivate your
players.

**STRICT RULES:**
- You are ONLY the neutral referee and storyteller. 
- NEVER roleplay as any player character, including yourself or any user.
- NEVER make decisions, take actions, or speak dialogue for any player character.
- Do NOT describe what player characters think, feel, say, or do. Only describe the world, NPCs, and the outcomes of player actions.
- You may narrate the results of dice rolls and adjudicate outcomes, but all choices and actions must come from the players.
- If a player asks "What do you propose we do?" or similar, do NOT answer as a character or suggest actions. Instead, prompt the players to decide.

**IMPORTANT:** Your entire reply (including formatting) must be 2000 characters or fewer to fit in a Discord message.

As the DM, you must:

1. **Be Smart:**
   - Create intricate plots with depth and nuance.
   - Develop complex non-player characters (NPCs) with unique motivations, personalities, and backstories.
   - Design challenging but fair encounters, including puzzles, traps, and combat scenarios.
   - Adapt to the players' actions and decisions, ensuring the story evolves dynamically.

2. **Be Persistent:**
   - Stay consistent in your world-building, maintaining continuity across sessions.
   - Remember the details of the game world, player characters, and previous events.
   - Maintain a logical progression of the story and challenges.

3. **Be Fun:**
   - Infuse humor, creativity, and excitement into the game.
   - Encourage role-playing by providing opportunities for players to interact with the game world in meaningful ways.
   - Balance serious storytelling with lighthearted moments.
   - Be ready to improvise when needed to keep the game flowing smoothly.

**Guidelines:**
- Assume you are running a campaign with 3–6 players, each playing one character. You will describe the game world, the situation, and any relevant rules or mechanics as needed.
- Provide clear descriptions of settings, characters, and events to help players visualize and immerse themselves
in the game.
- Encourage players to ask questions and explore their surroundings; respond with appropriate details.
- Be ready to adjudicate dice rolls (e.g., d20) and provide feedback on successes or failures.
- Keep the tone appropriate for all ages unless otherwise specified.

**Examples of DM Actions:**
1. Setting up an intriguing opening scene that hooks the players.
2. Creating a puzzle or riddle that challenges the players without being too frustrating.
3. Developing NPCs who react dynamically to player actions.
4. Introducing unexpected twists and turns in the story.
5. Balancing combat encounters with descriptive storytelling.

---

**Example of How the DM Might Begin:**

"Welcome, adventurers! You find yourselves standing at the edge of the ancient forest, shadows creeping between
the towering trees. The air is thick with mist, and an eerie silence hangs over the land. A village lies just
beyond the woods, but rumors say it has been abandoned after a strange curse began to spread. What do you do?"

"""

async def get_llm_response(prompt, prev_room=None):
    print(f"[DEBUG] get_llm_response called with prompt: {prompt}")
    full_prompt = f"{LLM_SYSTEM_PROMPT.strip()}\n\nPlayer: {prompt.strip()}"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "stream": False
                }
            )
            # --- Add this block to extract and return the LLM's reply ---
            if response.status_code == 200:
                data = response.json()
                # Try to get the response text from common keys
                if "response" in data:
                    return data["response"]
                elif "message" in data:
                    return data["message"]
                elif "text" in data:
                    return data["text"]
                else:
                    print("[Bot] LLM response JSON did not contain expected keys.")
                    return ""
            else:
                print(f"[Bot] Ollama returned status {response.status_code}: {response.text}")
                return ""
    except Exception as e:
        print("[Bot] Ollama chat failed:", e)
        return "The Dungeon Master is silent due to an error."

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"[Bot] Connected guilds: {[g.name for g in bot.guilds]}")
    print(f"[Bot] DISCORD_CHANNEL: {DISCORD_CHANNEL}")
    # Send the current world state to the configured channel on startup
    if DISCORD_CHANNEL:
        try:
            await bot.wait_until_ready()
            channel = bot.get_channel(int(DISCORD_CHANNEL))
            print(f"[DEBUG] get_channel({DISCORD_CHANNEL}) -> {channel}")
            if channel is None:
                channel = await bot.fetch_channel(int(DISCORD_CHANNEL))
                print(f"[DEBUG] fetch_channel({DISCORD_CHANNEL}) -> {channel}")
            if channel:
                # Compose the world state message
                world_msg = f"**Current Location:** {world_state['location']}\n\n{world_state['description']}"
                image_path = world_state.get("image")
                if image_path and os.path.exists(image_path):
                    with open(image_path, "rb") as img_fp:
                        discord_file = discord.File(img_fp, filename=os.path.basename(image_path))
                        await channel.send(world_msg, file=discord_file)
                else:
                    await channel.send(world_msg)
                print(f"[Bot] Sent world state to channel {DISCORD_CHANNEL}")
            else:
                print(f"[Bot] Could not find channel with ID {DISCORD_CHANNEL}")
        except Exception as e:
            print(f"[Bot] Failed to send world state: {e}")

def replace_mentions_with_handles(text, message):
    # Replace @user_id with @username in the DM output
    import re
    # Build a mapping of user IDs to handles for all mentioned users
    if hasattr(message, "mentions"):
        id_to_handle = {str(user.id): f"@{user.display_name}" for user in message.mentions}
        def repl(match):
            user_id = match.group(1)
            return id_to_handle.get(user_id, f"@{user_id}")
        # Replace patterns like @123456789012345678
        return re.sub(r"@(\d{17,20})", repl, text)
    return text

@bot.event
async def on_message(message):
    print(f"[DEBUG] on_message: author={message.author} channel={message.channel} id={getattr(message.channel, 'id', None)} content={message.content!r}")
    # Ignore messages from bots
    if message.author.bot:
        print("[DEBUG] Ignoring message from bot.")
        return

    # Only respond in the configured channel (if set)
    if DISCORD_CHANNEL and str(getattr(message.channel, "id", "")) != str(DISCORD_CHANNEL):
        print(f"[DEBUG] Message not in configured channel ({DISCORD_CHANNEL}), ignoring.")
        return

    # Respond to all messages in the channel if it's a DM, or if the bot is mentioned in a guild channel
    is_dm = isinstance(message.channel, discord.DMChannel)
    mentioned = bot.user in message.mentions if hasattr(message, "mentions") and message.mentions else False

    print(f"[DEBUG] is_dm={is_dm}, mentioned={mentioned}")
    if not is_dm and not mentioned:
        print("[DEBUG] Not a DM and bot not mentioned, ignoring.")
        return

    player = str(message.author)
    content = message.content.strip()
    if not content:
        print("[DEBUG] Empty content, ignoring.")
        return

    print(f"[DEBUG] Processing message from {player}: {content}")

    if player not in world_state["players"]:
        world_state["players"].append(player)
    chat_history.append({"sender": player, "message": content})

    # --- Movement logic: detect if the player wants to move to a new room ---
    prev_location = world_state["location"]
    prev_room_data = get_room(prev_location)

    # Try to match a movement command to an exit in the current room
    current_room = get_room(prev_location)
    exits = current_room.get("exits", []) if current_room else []
    new_location = None
    for exit_name in exits:
        if exit_name.lower() in content.lower():
            new_location = exit_name
            break

    if not new_location:
        match = re.search(r"\bgo (\w+)\b", content.lower())
        if match:
            direction = match.group(1).capitalize()
            new_location = direction

    if new_location:
        print(f"[DEBUG] Detected movement to: {new_location}")
        prev_location_key = get_room_key(prev_location)
        new_location_key = get_room_key(new_location)
        world_state["location"] = new_location
        save_game_state()  # <-- Persist the new location
        next_room = get_room(new_location)
        if next_room:
            world_state["description"] = next_room.get("description", world_state["description"])
            world_state["image"] = next_room.get("image")
        else:
            # --- Always create a new room with a description from the LLM and an exit back to the previous room ---
            world_state["description"] = ""
            world_state["image"] = None
            # Generate new room description
            server_message = await get_llm_response(f"You travel to {new_location}.", prev_room=prev_room_data)
            chat_history.append({"sender": "DM", "message": server_message})
            # Generate image for new room
            image_path = await ensure_world_image(new_location, server_message)
            world_state["image"] = image_path
            # Exits: add an exit back to the previous room
            exits = [prev_location] if prev_location else []
            # Try to extract more exits from the LLM response
            extracted_exits = extract_exits_from_dm(server_message)
            for e in extracted_exits:
                if e and e != prev_location and e not in exits:
                    exits.append(e)
            # Save new room to DB with all required fields
            set_room(
                new_location,
                {
                    "description": server_message,
                    "image": image_path,
                    "exits": exits,
                    "previous": prev_location_key if prev_location_key != new_location_key else None
                }
            )
            print(f"[DEBUG] Created new room: {new_location} with exits: {exits}")
            # Update world_state description for reply
            world_state["description"] = server_message

    async with message.channel.typing():
        room_data = get_room(world_state["location"])
        if room_data:
            server_message = room_data["description"]
            image_path = room_data.get("image")
            exits = room_data.get("exits", [])
            if not exits:
                exits = extract_exits_from_dm(server_message)
                if exits:
                    set_room(
                        world_state["location"],
                        {
                            "description": server_message,
                            "image": image_path,
                            "exits": exits,
                            "previous": room_data.get("previous")
                        }
                    )
            if not image_path or not os.path.exists(image_path):
                image_path = await ensure_world_image(world_state["location"], server_message)
                world_state["image"] = image_path
                set_room(
                    world_state["location"],
                    {
                        "description": server_message,
                        "image": image_path,
                        "exits": exits,
                        "previous": room_data.get("previous")
                    }
                )
            print(f"[DEBUG] Loaded existing room: {world_state['location']}")
        else:
            if not world_state["description"]:
                world_state["description"] = f"You arrive at {world_state['location']}."
            server_message = await get_llm_response(content, prev_room=prev_room_data)
            chat_history.append({"sender": "DM", "message": server_message})

            # --- Extract exits from DM output for new room initialization ---
            exits = extract_exits_from_dm(server_message)
            # Always (re)generate the image for the current location/description
            image_path = await ensure_world_image(world_state["location"], world_state["description"])
            world_state["image"] = image_path

            # Save new room to DB with exits initialized
            set_room(
                world_state["location"],
                {
                    "description": server_message,
                    "image": image_path,
                    "exits": exits,
                    "previous": get_room_key(prev_location) if prev_location != world_state["location"] else None
                }
            )
            print(f"[DEBUG] Saved new room: {world_state['location']}")

        # --- Remove <think>...</think> blocks from server_message ---
        if not isinstance(server_message, str):
            server_message = str(server_message) if server_message is not None else ""
        server_message_clean = re.sub(r"<think>.*?</think>", "", server_message, flags=re.DOTALL).strip()

        # If the LLM returned nothing, ensure reply is always '[No response from LLM]'
        if not server_message_clean:
            reply = "**DM:** [No response from LLM]"
        else:
            reply = f"**DM:** {server_message_clean}"

        # Replace @user_id with @username in the reply
        reply = replace_mentions_with_handles(reply, message)

        # Always append exits at the end
        if exits:
            reply = reply.rstrip()
            reply += "\n\n**Exits:** " + ", ".join(exits)

        # --- Send image first, then the reply (exits always at end) ---
        try:
            if image_path and os.path.exists(image_path):
                # Send the image first, centered, then the reply as a separate message
                with open(image_path, "rb") as img_fp:
                    discord_file = discord.File(img_fp, filename=os.path.basename(image_path))
                    # Center the image using Discord's markdown (centered effect is not guaranteed, but blank lines help visually)
                    await message.channel.send("\n", file=discord_file)
                await message.channel.send(reply)
            else:
                await message.channel.send(reply)
            print("[DEBUG] Sent reply to channel.")
        except Exception as e:
            print(f"[Bot] Failed to send message or image: {e}")

def run_async_task(coro, callback=None):
    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        if callback:
            callback(result)
    threading.Thread(target=runner, daemon=True).start()

if __name__ == "__main__":
    # Graceful shutdown handler for Ctrl+C
    def shutdown_handler(sig, frame):
        print("\n[Server] Caught Ctrl+C, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start Discord bot in the main thread (no GUI)
    if not DISCORD_TOKEN:
        print("[Bot] DISCORD_TOKEN is not set in the environment.")
    else:
        bot.run(DISCORD_TOKEN)
        print(f"[Bot] Failed to send message or image: {e}")
