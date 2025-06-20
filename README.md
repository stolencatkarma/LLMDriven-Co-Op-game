# LLMDriven Co-Op Game

A cooperative game prototype powered by Large Language Models (LLMs). Players interact with the game world and each other through natural language, with the LLM driving game logic, NPC behavior, and dynamic storytelling.

## Features

- Multiplayer co-op gameplay
- LLM-driven NPCs and world events
- Natural language command interface
- Modular and extensible game logic

## Getting Started

### Prerequisites

- Node.js (v18+ recommended)
- npm or yarn

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/LLMDriven-Co-Op-game.git
   cd LLMDriven-Co-Op-game
   ```
2. Install dependencies:
   ```
   npm install
   ```
3. Configure environment variables:
   - Create a `.env` file in the project root with the following content:
     ```
     OPENROUTER_API_KEY=''
     ```
   - **Do not hardcode API keys in the source code.** Always use environment variables for sensitive information.

### Running the Game

Start the development server:
```
npm run dev
```
or build and run:
```
npm run build
npm start
```

Access the game via your browser at `http://localhost:3000`.

## Usage

- Join or create a game session.
- Interact with the world and other players using natural language.
- The LLM interprets commands and advances the story dynamically.

## Project Structure

- `/src` - Main source code (game logic, server, client)
- `/public` - Static assets
- `/docs` - Documentation

## Contributing

Contributions are welcome! Please open issues or submit pull requests.

## License

MIT License
