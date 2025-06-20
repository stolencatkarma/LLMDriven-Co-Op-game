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
    global world_state, chat_history
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

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        if discord_channel:
            await send_initial_world_state()

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return
        if discord_channel and str(message.channel.id) != discord_channel:
            return
        
        await handle_player_message(message)

    async def send_initial_world_state():
        channel = bot.get_channel(int(discord_channel))
        if channel:
            world_msg = f"**Current Location:** {world_state['location']}\n\n{world_state['description']}"
            image_path = world_state.get("image")
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
            await handle_movement(message, new_location, prev_location)
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

    async def handle_movement(message, new_location: str, prev_location: str):
        world_state["location"] = new_location
        save_game_state(base_dir, new_location)
        
        next_room = get_room(new_location)
        if not next_room:
            await create_new_room(message, new_location, prev_location)
        else:
            update_world_state_from_room(next_room)
        
        await send_room_update(message.channel)

    async def create_new_room(message, new_location: str, prev_location: str):
        prev_room = get_room(prev_location)
        server_message = await get_llm_response(
            f"You travel to {new_location}.",
            ollama_host,
            ollama_model
        )
        
        image_path = await ensure_world_image(new_location, server_message, base_dir)
        exits = [prev_location] + extract_exits_from_dm(server_message)
        
        set_room(new_location, {
            "description": server_message,
            "image": image_path,
            "exits": exits,
            "previous": prev_location
        })
        
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
            chat_history.append({"sender": "DM", "message": server_message})
            
            room_data = get_room(world_state["location"]) or {}
            exits = extract_exits_from_dm(server_message)
            
            if exits:
                room_data["exits"] = exits
                set_room(world_state["location"], room_data)
            
            await send_dm_response(message.channel, server_message, exits)

    async def send_dm_response(channel, raw_message: str, exits: list):
        clean_message = re.sub(r"", "", raw_message, flags=re.DOTALL).strip()
        reply = f"**DM:** {replace_mentions(clean_message, channel)}"
        
        if exits:
            reply += f"\n\n**Exits:** {', '.join(exits)}"
        
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