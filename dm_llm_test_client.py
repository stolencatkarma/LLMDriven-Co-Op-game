import socket
import json
import threading
import time
import random

SERVER_HOST = "localhost"
SERVER_PORT = 65432

PLAYER_NAME = "TestBot"
CHARACTER_DESC = "A curious automaton with brass gears and glowing eyes."

ACTIONS = [
    "look around",
    "walk to the village",
    "inspect the ground",
    "talk to the nearest NPC",
    "draw my sword",
    "search for traps",
    "ask about the curse",
    "check my inventory",
    "listen carefully",
    "move quietly"
]

def receive_loop(sock):
    buffer = ""
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data.decode()
            while True:
                try:
                    msg, idx = json.JSONDecoder().raw_decode(buffer)
                    buffer = buffer[idx:].lstrip()
                except ValueError:
                    break
                msg_type = msg.get("type")
                if msg_type == "game_start":
                    print(f"\n--- GAME START ---\n{msg['message']}\n")
                elif msg_type == "your_turn":
                    print("\n[Bot] It's my turn!")
                    # Pick a random action and send it
                    action = random.choice(ACTIONS)
                    print(f"[Bot] Action: {action}")
                    play_msg = {
                        "action": "play",
                        "player_id": player_id,
                        "player_action": action
                    }
                    sock.sendall(json.dumps(play_msg).encode())
                elif msg_type == "wait":
                    print(f"[Bot] {msg['message']}")
                elif msg_type == "turn_result":
                    print(f"\n--- Turn Result ---")
                    print(f"{msg['player']} rolled a d20: {msg['roll']}")
                    print(f"Outcome: {msg['outcome']}")
                    print(f"DM: {msg['dm_response']}\n")
                elif msg_type == "chat":
                    print(f"[CHAT] {msg['sender']}: {msg['message']}")
                elif msg_type == "player_update":
                    print(f"[Bot] Inventory: {msg.get('inventory',[])} | Character: {msg.get('character','')}")
                elif msg_type == "game_log":
                    print(f"[Bot] Received game log update.")
                elif msg_type == "error":
                    print(f"[SERVER ERROR]: {msg['message']}")
                elif msg_type == "map_update":
                    print(f"[Bot] Received map update.")
        except Exception as e:
            print(f"[Bot] Connection error: {e}")
            break

OPENROUTER_API_KEY = "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"

if __name__ == "__main__":
    import os
    os.environ["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((SERVER_HOST, SERVER_PORT))
        register_msg = {
            "action": "register",
            "name": PLAYER_NAME,
            "character": CHARACTER_DESC
        }
        sock.sendall(json.dumps(register_msg).encode())
        response = json.loads(sock.recv(4096).decode())
        if response.get("status") != "registered":
            print("[Bot] Registration failed.")
            exit(1)
        player_id = response["player_id"]
        print(f"[Bot] Registered as player {player_id}. Waiting for the game to start...")
        threading.Thread(target=receive_loop, args=(sock,), daemon=True).start()
        # Keep the main thread alive
        while True:
            time.sleep(1)
