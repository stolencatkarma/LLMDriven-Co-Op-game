import json
import re

def get_room_key(location):
    return location.lower().replace(" ", "_")

def get_room(location):
    key = get_room_key(location)
    # Assumes rooms_db is set externally
    global rooms_db
    return rooms_db.get(key)

def set_room(location, data):
    key = get_room_key(location)
    global rooms_db
    rooms_db[key] = data
    save_rooms_db()

def set_rooms_db_path(path):
    """Set the global ROOMS_DB_PATH variable."""
    global ROOMS_DB_PATH
    ROOMS_DB_PATH = path

def save_rooms_db():
    # Assumes ROOMS_DB_PATH and rooms_db are set externally
    global ROOMS_DB_PATH, rooms_db
    if ROOMS_DB_PATH is None:
        raise RuntimeError(
            "ROOMS_DB_PATH is not set. Cannot save rooms database. "
            "Call set_rooms_db_path(pathlib.Path(...)) before using set_room()."
        )
    ROOMS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ROOMS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(rooms_db, f, indent=2)

def extract_exits_from_dm(dm_text):
    exits = []
    for line in dm_text.splitlines():
        match = re.match(r"(?i)(?:obvious )?exits?:\s*(.*)", line)
        if match:
            exits = [e.strip() for e in match.group(1).split(",") if e.strip()]
            break
    return exits

# These globals must be set by the main server module:
rooms_db = {}
ROOMS_DB_PATH = None
