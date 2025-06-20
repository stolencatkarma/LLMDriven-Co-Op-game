import socket
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, Toplevel, Listbox, END
from PIL import Image, ImageTk
import io
import base64

SERVER_HOST = "localhost"
SERVER_PORT = 65432

class DMClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("D20 Co-Op Client")
        # Main game text area
        self.text_area = scrolledtext.ScrolledText(master, state='disabled', width=60, height=15)
        self.text_area.pack(padx=10, pady=5)
        # Game log/history
        self.log_area = scrolledtext.ScrolledText(master, state='disabled', width=60, height=8, bg="#f0f0f0")
        self.log_area.pack(padx=10, pady=(0,5))
        # Scene image
        self.image_label = tk.Label(master)
        self.image_label.pack(padx=10, pady=(0,10))
        # Portrait image
        self.portrait_label = tk.Label(master)
        self.portrait_label.pack(padx=10, pady=(0,10))
        # Map/world visualization
        self.map_label = tk.Label(master)
        self.map_label.pack(padx=10, pady=(0,10))
        self.map_b64 = None
        # Action entry
        self.entry = tk.Entry(master, width=40)
        self.entry.pack(side=tk.LEFT, padx=(10,0), pady=(0,10))
        self.send_btn = tk.Button(master, text="Send Action", command=self.send_action, state='disabled')
        self.send_btn.pack(side=tk.LEFT, padx=5, pady=(0,10))
        # Chat entry
        self.chat_entry = tk.Entry(master, width=25)
        self.chat_entry.pack(side=tk.LEFT, padx=(10,0), pady=(0,10))
        self.chat_btn = tk.Button(master, text="Send Chat", command=self.send_chat)
        self.chat_btn.pack(side=tk.LEFT, padx=5, pady=(0,10))
        # Inventory/character sheet button
        self.inv_btn = tk.Button(master, text="Inventory/Sheet", command=self.show_inventory)
        self.inv_btn.pack(side=tk.LEFT, padx=5, pady=(0,10))
        # Game log button
        self.log_btn = tk.Button(master, text="Show Log", command=self.request_game_log)
        self.log_btn.pack(side=tk.LEFT, padx=5, pady=(0,10))
        self.sock = None
        self.player_id = None
        self.state = {"your_turn": False}
        self.inventory = []
        self.character = ""
        self.avatar_b64 = None
        self.connect_to_server()

    def connect_to_server(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((SERVER_HOST, SERVER_PORT))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
            self.master.destroy()
            return
        name = simpledialog.askstring("Player Name", "Enter your player name:", parent=self.master)
        character = simpledialog.askstring("Character", "Describe your character:", parent=self.master)
        register_msg = {
            "action": "register",
            "name": name,
            "character": character
        }
        self.sock.sendall(json.dumps(register_msg).encode())
        response = json.loads(self.sock.recv(4096).decode())
        if response.get("status") != "registered":
            messagebox.showerror("Registration Failed", "Registration failed.")
            self.master.destroy()
            return
        self.player_id = response["player_id"]
        # Show avatar/portrait if present
        if "avatar" in response and response["avatar"]:
            self.show_avatar(response["avatar"])
            self.avatar_b64 = response["avatar"]
        self.append_text(f"Registered as player {self.player_id}. Waiting for the game to start...\n")
        threading.Thread(target=self.listen_to_server, daemon=True).start()

    def listen_to_server(self):
        buffer = ""
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data.decode()
                # Handle multiple JSON objects in the buffer
                while True:
                    try:
                        msg, idx = json.JSONDecoder().raw_decode(buffer)
                        buffer = buffer[idx:].lstrip()
                    except ValueError:
                        break  # Not enough data to decode a full message
                    msg_type = msg.get("type")
                    if msg_type == "game_start":
                        self.append_text(f"\n--- GAME START ---\n{msg['message']}\n")
                    elif msg_type == "your_turn":
                        self.append_text("\nIt's your turn!\n")
                        self.state["your_turn"] = True
                        self.send_btn.config(state='normal')
                    elif msg_type == "wait":
                        self.append_text(f"\n{msg['message']}\n")
                        self.state["your_turn"] = False
                        self.send_btn.config(state='disabled')
                    elif msg_type == "turn_result":
                        self.append_text(f"\n--- Turn Result ---\n")
                        self.append_text(f"{msg['player']} rolled a d20: {msg['roll']}\n")
                        self.append_text(f"Outcome: {msg['outcome']}\n")
                        self.append_text(f"DM: {msg['dm_response']}\n\n")
                        if msg.get("scene_image"):
                            self.show_image(msg["scene_image"])
                        else:
                            self.clear_image()
                    elif msg_type == "chat":
                        self.append_text(f"[CHAT] {msg['sender']}: {msg['message']}\n")
                    elif msg_type == "player_update":
                        self.inventory = msg.get("inventory", [])
                        self.character = msg.get("character", "")
                        if msg.get("avatar"):
                            self.show_avatar(msg["avatar"])
                            self.avatar_b64 = msg["avatar"]
                    elif msg_type == "game_log":
                        self.show_log(msg.get("log", []))
                    elif msg_type == "error":
                        self.append_text(f"\n[SERVER ERROR]: {msg['message']}\n")
                    elif msg_type == "map_update":
                        if msg.get("map_image"):
                            self.show_map(msg["map_image"])
                            self.map_b64 = msg["map_image"]
                        else:
                            self.clear_map()
            except Exception as e:
                self.append_text(f"Connection error: {e}\n")
                break

    def send_action(self):
        action = self.entry.get().strip()
        if not action:
            return
        play_msg = {
            "action": "play",
            "player_id": self.player_id,
            "player_action": action
        }
        try:
            self.sock.sendall(json.dumps(play_msg).encode())
        except Exception as e:
            self.append_text(f"Send error: {e}\n")
        self.entry.delete(0, tk.END)
        self.state["your_turn"] = False
        self.send_btn.config(state='disabled')

    def send_chat(self):
        chat_msg = self.chat_entry.get().strip()
        if not chat_msg:
            return
        msg = {
            "action": "chat",
            "sender": f"Player {self.player_id}",
            "message": chat_msg
        }
        try:
            self.sock.sendall(json.dumps(msg).encode())
        except Exception as e:
            self.append_text(f"Chat send error: {e}\n")
        self.chat_entry.delete(0, tk.END)

    def show_inventory(self):
        # Request latest inventory/character sheet
        self.sock.sendall(json.dumps({"action": "request_inventory", "player_id": self.player_id}).encode())
        inv_win = Toplevel(self.master)
        inv_win.title("Inventory & Character Sheet")
        tk.Label(inv_win, text="Character:").pack()
        tk.Message(inv_win, text=self.character, width=300).pack()
        tk.Label(inv_win, text="Inventory:").pack()
        lb = Listbox(inv_win, width=40)
        lb.pack()
        for item in self.inventory:
            lb.insert(END, item)

    def request_game_log(self):
        self.sock.sendall(json.dumps({"action": "request_game_log", "player_id": self.player_id}).encode())

    def show_log(self, log):
        log_win = Toplevel(self.master)
        log_win.title("Game Log / History")
        log_text = scrolledtext.ScrolledText(log_win, state='normal', width=60, height=20)
        log_text.pack()
        for entry_type, entry in log:
            if entry_type == "chat":
                log_text.insert(END, f"[CHAT] {entry}\n")
            elif entry_type == "system":
                log_text.insert(END, f"[SYSTEM] {entry}\n")
            else:
                log_text.insert(END, f"{entry}\n")
        log_text.config(state='disabled')

    def append_text(self, text):
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.config(state='disabled')

    def show_image(self, b64_png):
        try:
            img_data = base64.b64decode(b64_png)
            image = Image.open(io.BytesIO(img_data))
            image = image.resize((256, 256))
            self.tk_image = ImageTk.PhotoImage(image)
            self.image_label.config(image=self.tk_image)
        except Exception as e:
            self.append_text(f"Image error: {e}\n")
            self.clear_image()

    def clear_image(self):
        self.image_label.config(image='')

    def show_avatar(self, b64_png):
        try:
            img_data = base64.b64decode(b64_png)
            image = Image.open(io.BytesIO(img_data))
            image = image.resize((128, 128))
            self.tk_avatar = ImageTk.PhotoImage(image)
            self.portrait_label.config(image=self.tk_avatar)
        except Exception as e:
            self.append_text(f"Avatar error: {e}\n")
            self.portrait_label.config(image='')

    def show_map(self, b64_png):
        try:
            img_data = base64.b64decode(b64_png)
            image = Image.open(io.BytesIO(img_data))
            image = image.resize((256, 256))
            self.tk_map = ImageTk.PhotoImage(image)
            self.map_label.config(image=self.tk_map)
        except Exception as e:
            self.append_text(f"Map error: {e}\n")
            self.clear_map()

    def clear_map(self):
        self.map_label.config(image='')

def main():
    root = tk.Tk()
    app = DMClientGUI(root)
    def on_close():
        try:
            app.sock.close()
        except Exception:
            pass
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)
    # Add Ctrl+C support for clean exit
    def handle_ctrl_c(*args):
        on_close()
    import signal
    signal.signal(signal.SIGINT, handle_ctrl_c)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        on_close()

if __name__ == "__main__":
    main()
