# LLM-Driven Co-Op D20 Game

A cooperative adventure game for 2-4 players, with an LLM acting as Dungeon Master and referee. The system uses a SQLite3 database to ensure consistent memory and world state.

## Features

- D20-based rules (generic, open source)
- LLM as Dungeon Master (DM)
- Persistent memory and world state via SQLite3
- Player inventory and character tracking
- Room/area connections for exploration
- All dice rolls are d20 (1 = fail, 20 = success)

## Getting Started

1. Install Python 3.8+.
2. Install dependencies: `pip install openai`
3. Set your OpenAI API key as the environment variable `OPENAI_API_KEY`.
4. Run `dm_database.py` once to initialize the database.
5. Start the game with `python dm_game.py`.

## How to Start

1. Make sure you have run `dm_database.py` at least once to set up the database:
   ```
   python dm_database.py
   ```
2. Start the game loop:
   ```
   python dm_game.py
   ```

## Project Structure

- `dm_database.py` — Database schema and helper functions
- `dm_game.py` — LLM integration and main game loop

## License

Open source, for educational and personal use.
