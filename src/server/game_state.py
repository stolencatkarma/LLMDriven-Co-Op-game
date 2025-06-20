import json
from pathlib import Path

def save_game_state(base_dir: Path, location: str):
    game_state_path = base_dir / "db" / "game_state.json"
    game_state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(game_state_path, "w", encoding="utf-8") as f:
        json.dump({"location": location}, f)

def load_game_state(base_dir: Path):
    game_state_path = base_dir / "db" / "game_state.json"
    if game_state_path.exists():
        with open(game_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("location")
    return None