import os
import signal
import sys
from pathlib import Path
from dotenv import load_dotenv

from room_utils import set_rooms_db_path
from discord_bot import init_bot

# Load environment variables from .env file
load_dotenv()

# Configuration from environment
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL = os.getenv("DISCORD_CHANNEL")  # Optional channel ID restriction

# Path configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
set_rooms_db_path(BASE_DIR / "db" / "rooms.json")

if __name__ == "__main__":
    print("[DEPRECATED] Please run the server using: python src/server/run_server.py")
    print("This entry point is deprecated and will be removed in the future.")
    # Optionally, you could call run_server.main() here for backward compatibility
    # from run_server import main; main()
