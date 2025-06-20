import os
import random
import openai
import sqlite3
import socket
import threading
import json
import base64
import requests
from dm_database import (
    init_db, add_player, log_dice_roll, log_memory, get_memories_by_keywords
)
# Add imports for persistent save/load
import pickle

openai.api_key = os.getenv("OPENAI_API_KEY")
DB_PATH = "dm_game.db"

def roll_d20():
    return random.randint(1, 20)

# Use a robust, detailed system prompt for the LLM Dungeon Master.
DM_SYSTEM_PROMPT = """
You are a highly intelligent, experienced, and creative Dungeon Master for a D20-based tabletop role-playing game.
Your goal is to create an engaging, immersive, and memorable experience for the players. You are responsible for managing the game world, creating encounters, adjudicating rules, and telling stories that captivate your players.

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
- Provide clear descriptions of settings, characters, and events to help players visualize and immerse themselves in the game.
- Encourage players to ask questions and explore their surroundings; respond with appropriate details.
- Be ready to adjudicate dice rolls (e.g., d20) and provide feedback on successes or failures.
- Keep the tone appropriate for all ages unless otherwise specified.

**Examples of DM Actions:**
1. Setting up an intriguing opening scene that hooks the players.
2. Creating a puzzle or riddle that challenges the players without being too frustrating.
3. Developing NPCs who react dynamically to player actions.
4. Introducing unexpected twists and turns in the story.
5. Balancing combat encounters with descriptive storytelling.

**Consistency and Memory:**
- You must remember every decision and stick to it. Never contradict previous events or outcomes.
- Use keywords and summaries to recall important memories and world state.
- Understand and track past, present, and future actions of all players and NPCs.
- Track player inventories, character details, and the state of the world persistently.

**Immersion:**
- Use vivid, sensory-rich descriptions.
- Make the world feel alive and responsive to player actions.
- Always provide enough detail for players to make informed decisions.

--- End of system prompt ---
"""

OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "deepseek/deepseek-r1:free"

def get_dm_response(prompt, memories):
    context = "Relevant memories:\n"
    for mem in memories[:5]:
        context += f"- {mem[2]}: {mem[3]}\n"
    context += "\n"
    context += prompt
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": DM_SYSTEM_PROMPT},
            {"role": "user", "content": context}
        ],
        "max_tokens": 300
    }
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"OpenRouter API error: {e}")
        return "The Dungeon Master is silent due to an error."

def get_player_by_id(player_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, character_details FROM players WHERE id = ?", (player_id,))
    result = c.fetchone()
    conn.close()
    return result if result else ("Unknown", "")

def generate_scene_image(description):
    """
    Use an image generation API (e.g., OpenAI DALL·E, Stable Diffusion, etc.)
    to generate a PNG image for the scene description.
    Returns the PNG image bytes, or None if generation fails.
    """
    try:
        dalle_response = openai.images.generate(
            model="dall-e-3",
            prompt=description,
            n=1,
            size="1024x1024"
        )
        image_url = dalle_response.data[0].url
        img_response = requests.get(image_url)
        if img_response.status_code == 200:
            return img_response.content
    except Exception as e:
        print(f"Image generation failed: {e}")
    return None

def generate_avatar_image(character_description):
    """
    Use an image generation API to generate a PNG avatar for the character.
    Returns the PNG image bytes, or None if generation fails.
    """
    try:
        dalle_response = openai.images.generate(
            model="dall-e-3",
            prompt=f"portrait of {character_description}, fantasy character, headshot, centered, detailed, digital art",
            n=1,
            size="512x512"
        )
        image_url = dalle_response.data[0].url
        img_response = requests.get(image_url)
        if img_response.status_code == 200:
            return img_response.content
    except Exception as e:
        print(f"Avatar generation failed: {e}")
    return None

# Make sure generate_map_image is defined before it is used
def generate_map_image(map_description):
    """
    Use an image generation API to generate a PNG map for the current world/area.
    Returns the PNG image bytes, or None if generation fails.
    """
    try:
        dalle_response = openai.images.generate(
            model="dall-e-3",
            prompt=f"fantasy map, {map_description}, digital art, top-down, simple, colorful",
            n=1,
            size="512x512"
        )
        image_url = dalle_response.data[0].url
        img_response = requests.get(image_url)
        if img_response.status_code == 200:
            return img_response.content
    except Exception as e:
        print(f"Map generation failed: {e}")
    return None

GAME_STATE_FILE = "game_state.pkl"
MAP_STATE_FILE = "map_state.b64"

def save_game_state(players, inventories, game_log, avatars, current_map_b64):
    # Save all persistent state to disk
    with open(GAME_STATE_FILE, "wb") as f:
        pickle.dump({
            "players": [(p["id"], p["name"]) for p in players],
            "inventories": inventories,
            "game_log": game_log,
            "avatars": avatars
        }, f)
    if current_map_b64:
        with open(MAP_STATE_FILE, "w") as f:
            f.write(current_map_b64)

def load_game_state():
    players, inventories, game_log, avatars, map_b64 = None, None, None, None, None
    if os.path.exists(GAME_STATE_FILE):
        try:
            with open(GAME_STATE_FILE, "rb") as f:
                state = pickle.load(f)
                players = state.get("players")
                inventories = state.get("inventories")
                game_log = state.get("game_log")
                avatars = state.get("avatars")
        except Exception:
            pass
    if os.path.exists(MAP_STATE_FILE):
        try:
            with open(MAP_STATE_FILE, "r") as f:
                map_b64 = f.read()
        except Exception:
            pass
    return players, inventories, game_log, avatars, map_b64

class GameServer:
    def __init__(self, host="localhost", port=65432):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.players = []  # List of dicts: {"conn":..., "addr":..., "id":..., "name":...}
        self.turn = 0
        self.lock = threading.Lock()
        self.game_started = False
        self.game_log = []  # Store tuples: (type, message)
        self.inventories = {}  # player_id -> list of items
        self.avatars = {}  # player_id -> base64 avatar
        self.current_map_b64 = None  # base64 PNG of the current map
        # Load persistent state if available
        loaded_players, loaded_inventories, loaded_log, loaded_avatars, loaded_map = load_game_state()
        if loaded_players is not None:
            for pid, name in loaded_players:
                self.players.append({"conn": None, "addr": None, "id": pid, "name": name})
            self.inventories = loaded_inventories or {}
            self.game_log = loaded_log or []
            self.avatars = loaded_avatars or {}
            self.current_map_b64 = loaded_map

    def broadcast(self, message):
        for player in self.players:
            try:
                player["conn"].sendall(json.dumps(message).encode())
            except:
                pass

    def send_player_update(self, player):
        # Send inventory and character details to a player
        name, char_details = get_player_by_id(player["id"])
        inventory = self.inventories.get(player["id"], [])
        avatar = self.avatars.get(player["id"])
        msg = {
            "type": "player_update",
            "character": char_details,
            "inventory": inventory,
            "avatar": avatar
        }
        try:
            player["conn"].sendall(json.dumps(msg).encode())
        except:
            pass

    def broadcast_map(self, map_b64):
        self.broadcast({"type": "map_update", "map_image": map_b64})

    def handle_client(self, conn, addr):
        player_id = None
        player_name = None
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                request = json.loads(data.decode())
                action = request.get("action")
                if action == "register":
                    name = request["name"]
                    char_details = request["character"]
                    with self.lock:
                        add_player(name, char_details)
                        player_id = len(self.players) + 1
                        player_name = name
                        self.players.append({"conn": conn, "addr": addr, "id": player_id, "name": name})
                        self.inventories.setdefault(player_id, [])
                        # Generate avatar/portrait for this character
                        avatar_bytes = generate_avatar_image(char_details)
                        avatar_b64 = base64.b64encode(avatar_bytes).decode("utf-8") if avatar_bytes else None
                        self.avatars[player_id] = avatar_b64
                        response = {"status": "registered", "player_id": player_id, "avatar": avatar_b64}
                        conn.sendall(json.dumps(response).encode())
                        print(f"Registered player {name} (id={player_id}) from {addr}")
                        # After registration, send the current map if available
                        if self.current_map_b64:
                            try:
                                conn.sendall(json.dumps({"type": "map_update", "map_image": self.current_map_b64}).encode())
                            except:
                                pass
                        # Immediately start game for this player if not already started
                        if not self.game_started:
                            self.game_started = True
                            opening = (
                                "You find yourselves at the edge of an ancient forest. "
                                "Mist swirls around your feet. A village lies ahead, rumored to be cursed. What do you do?"
                            )
                            log_memory("opening,forest,village", "Game begins at forest edge", opening)
                            self.game_log.append(("system", opening))
                            self.broadcast({"type": "game_start", "message": opening})
                        self.notify_turn()
                        self.send_player_update(self.players[-1])
                        conn.sendall(json.dumps({"type": "game_log", "log": self.game_log}).encode())
                        # Save state after registration
                        save_game_state(self.players, self.inventories, self.game_log, self.avatars, self.current_map_b64)
                    continue
                elif action == "play":
                    with self.lock:
                        if not self.players or self.players[self.turn % len(self.players)]["id"] != player_id:
                            conn.sendall(json.dumps({"type": "error", "message": "Not your turn."}).encode())
                            continue
                        name, char_details = get_player_by_id(player_id)
                        player_action = request["player_action"]
                        roll = roll_d20()
                        outcome = "Success" if roll == 20 else "Failure" if roll == 1 else "Check DM response"
                        log_dice_roll(player_id, player_action, roll, outcome)
                        log_memory(f"action,{name}", f"{name} acts", player_action)
                        memories = get_memories_by_keywords(name)
                        dm_prompt = (
                            f"Player: {name} ({char_details})\n"
                            f"Action: {player_action}\n"
                            f"Dice roll: {roll}\n"
                            f"Outcome: {outcome}\n"
                            "Describe what happens next."
                        )
                        dm_response = get_dm_response(dm_prompt, memories)
                        log_memory("dm_response", f"DM response to {name}", dm_response)
                        image_bytes = generate_scene_image(dm_response)
                        image_b64 = base64.b64encode(image_bytes).decode("utf-8") if image_bytes else None
                        # Optionally, update the map based on DM response or player action
                        # For demo: regenerate map every turn using DM response as context
                        map_bytes = generate_map_image(dm_response)
                        map_b64 = base64.b64encode(map_bytes).decode("utf-8") if map_bytes else None
                        if map_b64:
                            self.current_map_b64 = map_b64
                            self.broadcast_map(map_b64)
                        if "finds a" in dm_response or "finds an" in dm_response:
                            item = dm_response.split("finds a")[-1].split()[0] if "finds a" in dm_response else dm_response.split("finds an")[-1].split()[0]
                            self.inventories[player_id].append(item)
                            self.send_player_update(self.players[self.turn % len(self.players)])
                        self.game_log.append(("turn", f"{name} ({char_details}) rolled {roll}: {player_action} -> {outcome}\nDM: {dm_response}"))
                        self.broadcast({
                            "type": "turn_result",
                            "player": name,
                            "roll": roll,
                            "outcome": outcome,
                            "dm_response": dm_response,
                            "scene_image": image_b64
                        })
                        self.broadcast({"type": "game_log", "log": self.game_log})
                        self.turn += 1
                        self.players = [p for p in self.players if p["conn"] is None or p["conn"].fileno() != -1]
                        if self.players:
                            self.notify_turn()
                        # Save state after each turn
                        save_game_state(self.players, self.inventories, self.game_log, self.avatars, self.current_map_b64)
                    continue
                elif action == "chat":
                    chat_msg = request.get("message", "")
                    sender = request.get("sender", f"Player {player_id}")
                    chat_entry = ("chat", f"{sender}: {chat_msg}")
                    self.game_log.append(chat_entry)
                    self.broadcast({"type": "chat", "sender": sender, "message": chat_msg})
                    self.broadcast({"type": "game_log", "log": self.game_log})
                    # Save state after chat
                    save_game_state(self.players, self.inventories, self.game_log, self.avatars, self.current_map_b64)
                    continue
                elif action == "request_inventory":
                    with self.lock:
                        for p in self.players:
                            if p["id"] == player_id:
                                self.send_player_update(p)
                                break
                    continue
                elif action == "request_game_log":
                    with self.lock:
                        conn.sendall(json.dumps({"type": "game_log", "log": self.game_log}).encode())
                    continue
            except Exception as e:
                print(f"Error: {e}")
                break
        conn.close()
        print(f"Client disconnected: {addr}")
        with self.lock:
            self.players = [p for p in self.players if p["conn"] != conn]
            if self.players:
                self.turn = self.turn % len(self.players)
                self.notify_turn()
            # Save state after disconnect
            save_game_state(self.players, self.inventories, self.game_log, self.avatars, self.current_map_b64)

    def notify_turn(self):
        if not self.players:
            return
        current_player = self.players[self.turn % len(self.players)]
        for player in self.players:
            if player["id"] == current_player["id"]:
                msg = {"type": "your_turn", "message": "It's your turn!"}
            else:
                msg = {"type": "wait", "message": f"Waiting for {current_player['name']} to act."}
            try:
                player["conn"].sendall(json.dumps(msg).encode())
            except:
                pass

    def run(self):
        init_db()
        self.server.bind((self.host, self.port))
        self.server.listen()
        print(f"LLM Dungeon Master server listening on {self.host}:{self.port}")
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

def main():
    import signal
    import sys
    def handle_ctrl_c(sig, frame):
        print("\nServer stopped by user.")
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_ctrl_c)
    try:
        GameServer().run()
    except KeyboardInterrupt:
        print("\nServer stopped by user.")

if __name__ == "__main__":
    main()
