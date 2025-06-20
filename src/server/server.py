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
    # Graceful shutdown handler for Ctrl+C
    def shutdown_handler(sig, frame):
        print("\n[Server] Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    if DISCORD_TOKEN:
        init_bot(
            discord_token=DISCORD_TOKEN,
            discord_channel=DISCORD_CHANNEL,
            base_dir=BASE_DIR,
            ollama_host=OLLAMA_HOST,
            ollama_model=OLLAMA_MODEL
        )
    else:
        print("DISCORD_TOKEN is required in environment variables")
