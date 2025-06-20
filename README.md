# LLM-Driven Co-Op Game Server

This project is a Discord-based, AI-powered tabletop RPG engine. It uses a Large Language Model (LLM) to act as the Game Master (GM), generating story, encounters, and world content dynamically. The system is designed for collaborative, co-op play, with a focus on narrative-driven campaigns and DM/LLM co-creation.

## Features

- **Discord Bot**: Players interact with the game via Discord commands and chat.
- **LLM Game Master**: The LLM generates campaign stories, adventures, NPCs, and world descriptions.
- **Session Zero**: Players create characters in a guided onboarding phase.
- **Campaign State Machine**: The bot tracks campaign phases: pre-session zero, session zero, campaign started, and adventure running.
- **Adventure Summaries**: Each campaign is scaffolded with 3-5 short adventure summaries, which are expanded into full adventures as the campaign progresses.
- **Image Generation**: Room and world images are generated using Stable Diffusion WebUI and sent to Discord.
- **DM/LLM Collaboration**: DMs can provide campaign and adventure outlines to guide the LLM.
- **Extensible Commands**: Modular command system for rolling, moving, shopping, and more.

## Getting Started

### Prerequisites

- Python 3.10+
- Discord bot token
- [Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) running locally for image generation (API enabled)
- Ollama or compatible LLM server for story generation

### Setup

1. Clone this repository.
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Discord bot token and other settings:
   ```env
   DISCORD_TOKEN=your_token_here
   DISCORD_CHANNEL=your_channel_id
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=deepseek
   ```
4. (Optional) Add your own campaign or adventure outlines as Markdown files in `example_campaigns/` or `example_adventures/`.
5. Run the server:
   ```sh
   python run_server.py
   ```

## How It Works

- On first run, the bot creates a campaign (inspired by your example files if present) and enters Session Zero for character creation.
- Players create characters via DM with the bot.
- The DM starts the campaign with `!startcampaign` in the Discord channel.
- The campaign is divided into adventures, each with a summary. The LLM expands these into full adventures as the game progresses.
- Use `!startadventure` to begin the next adventure when ready.
- The bot manages world state, player actions, and generates images for locations.

## Key Commands

- `!startcampaign` — Start the campaign after all players have created characters.
- `!startadventure` — Begin the next adventure.
- `!move <destination>` — Move to a new location.
- `!roll` — Roll dice.
- `!buy`, `!sell`, `!shop` — Shop commands.
- `!equip`, `!equipment` — Manage gear.
- `!players` — List current players.
- `!help` — Show help.

## File Structure

- `run_server.py` — Main entry point.
- `src/server/discord_bot.py` — Discord bot and game logic.
- `src/server/commands/` — Modular command handlers.
- `db/` — Persistent game state (campaign, characters, rooms, images).
- `example_campaigns/`, `example_adventures/` — Example campaign/adventure outlines for the LLM.

## Customization

- Add or edit Markdown files in `example_campaigns/` or `example_adventures/` to guide the LLM's campaign and adventure generation.
- Edit `campaign.json` to provide your own adventure summaries or descriptions.

## Troubleshooting

- **Images not showing up?** Ensure Stable Diffusion WebUI is running with the API enabled and the bot has permission to send files in your Discord channel.
- **LLM not responding?** Check your Ollama/LLM server is running and accessible.
- **Bot not responding to commands?** Check your `.env` file and Discord permissions.

## License

MIT
