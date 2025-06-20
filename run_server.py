import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure src/server is in sys.path for module resolution
sys.path.insert(0, str(Path(__file__).parent / "src" / "server"))

from room_utils import set_rooms_db_path
from discord_bot import init_bot

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="LLM-Driven Co-Op Game Server")
    parser.add_argument('--discord-token', type=str, default=os.getenv("DISCORD_TOKEN"), help='Discord bot token')
    parser.add_argument('--discord-channel', type=str, default=os.getenv("DISCORD_CHANNEL"), help='Discord channel ID (optional)')
    parser.add_argument('--ollama-host', type=str, default=os.getenv("OLLAMA_HOST", "http://localhost:11434"), help='Ollama host URL')
    parser.add_argument('--ollama-model', type=str, default=os.getenv("OLLAMA_MODEL", "deepseek"), help='Ollama model name')
    parser.add_argument('--base-dir', type=str, default=str(Path(__file__).resolve().parent), help='Base directory for data')
    args = parser.parse_args()

    BASE_DIR = Path(args.base_dir)
    set_rooms_db_path(BASE_DIR / "db" / "rooms.json")

    if not args.discord_token:
        print("DISCORD_TOKEN is required. Set it in your .env file or pass with --discord-token.")
        sys.exit(1)

    print("[Server] Starting Discord bot...")
    try:
        init_bot(
            discord_token=args.discord_token,
            discord_channel=args.discord_channel,
            base_dir=BASE_DIR,
            ollama_host=args.ollama_host,
            ollama_model=args.ollama_model
        )
    except Exception as e:
        import traceback
        print("[ERROR] Exception during bot startup:")
        traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
