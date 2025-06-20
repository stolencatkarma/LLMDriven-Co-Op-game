import sqlite3
from datetime import datetime

DB_PATH = "dm_game.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Players table
    c.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            character_details TEXT,
            inventory TEXT
        )
    ''')
    # Rooms table
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT
        )
    ''')
    # Room connections
    c.execute('''
        CREATE TABLE IF NOT EXISTS room_connections (
            from_room INTEGER,
            to_room INTEGER,
            direction TEXT,
            FOREIGN KEY(from_room) REFERENCES rooms(id),
            FOREIGN KEY(to_room) REFERENCES rooms(id)
        )
    ''')
    # Memories/events table
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            keywords TEXT,
            summary TEXT,
            details TEXT
        )
    ''')
    # Dice rolls table
    c.execute('''
        CREATE TABLE IF NOT EXISTS dice_rolls (
            id INTEGER PRIMARY KEY,
            player_id INTEGER,
            action TEXT,
            roll INTEGER,
            outcome TEXT,
            timestamp TEXT,
            FOREIGN KEY(player_id) REFERENCES players(id)
        )
    ''')
    conn.commit()
    conn.close()

def add_player(name, character_details):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO players (name, character_details, inventory) VALUES (?, ?, ?)', (name, character_details, ''))
    conn.commit()
    conn.close()

def add_room(name, description):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO rooms (name, description) VALUES (?, ?)', (name, description))
    conn.commit()
    conn.close()

def connect_rooms(from_room, to_room, direction):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO room_connections (from_room, to_room, direction) VALUES (?, ?, ?)', (from_room, to_room, direction))
    conn.commit()
    conn.close()

def log_memory(keywords, summary, details):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO memories (timestamp, keywords, summary, details) VALUES (?, ?, ?, ?)',
              (datetime.utcnow().isoformat(), keywords, summary, details))
    conn.commit()
    conn.close()

def log_dice_roll(player_id, action, roll, outcome):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO dice_rolls (player_id, action, roll, outcome, timestamp) VALUES (?, ?, ?, ?, ?)',
              (player_id, action, roll, outcome, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_memories_by_keywords(keywords):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT * FROM memories WHERE keywords LIKE ? ORDER BY timestamp DESC"
    c.execute(query, ('%' + keywords + '%',))
    results = c.fetchall()
    conn.close()
    return results

# ...add more helper functions as needed...
