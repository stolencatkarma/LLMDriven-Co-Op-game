import os
import httpx
from pathlib import Path

LLM_SYSTEM_PROMPT = """
You are a creative, fair, and engaging Dungeon Master for a D20-based tabletop RPG set in a dystopian sci-fi Mega City and its wasteland. Your job is to describe the world, NPCs, and outcomes of player actions, never controlling or speaking for player characters.

**Setting:**
- The Mega City Verisium is a neon-lit metropolis of advanced tech, cybernetics, powerful corporations, and stark class divides. The wasteland outside is dangerous and lawless. Magic is rare or replaced by psionics and science. All locations, NPCs, and events should fit this world.

**Rules:**
- Only narrate the world, NPCs, and results of player actions.
- Never roleplay, decide for, or speak as any player character.
- Do not describe what player characters think, feel, say, or do.
- If asked for suggestions, prompt the players to decide.
- Keep all responses under 2000 characters for Discord.

**Be Smart:**
- Create interesting plots, NPCs, and challenges.
- Adapt to player actions and keep the world consistent.
- Balance fun, challenge, and story.
"""

async def get_llm_response(prompt: str, ollama_host: str, ollama_model: str) -> str:
    full_prompt = f"{LLM_SYSTEM_PROMPT.strip()}\n\nPlayer: {prompt.strip()}"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{ollama_host}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": full_prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response") or data.get("message") or data.get("text") or ""
            else:
                print(f"LLM error: {response.status_code} - {response.text}")
                return ""
    except Exception as e:
        print(f"LLM request failed: {e}")
        return ""

async def llm_can_equip(character, item, ollama_host, ollama_model):
    """
    Ask the LLM if the character can equip the item, and in which slot. Returns dict:
    { 'allowed': bool, 'slot': str or None, 'reason': str }
    """
    prompt = f"""
A player wishes to equip an item. Here is their character sheet:
Name: {character.name}\nRace: {character.race}\nClass: {character.char_class}\nAbilities: {character.abilities}\nInventory: {character.inventory}\nEquipped: {character.equipped}\n
The player says: 'equip my {item}'.

As the DM, decide if this character can equip this item, considering their race, class, and any reasonable fantasy logic. If allowed, specify the equipment slot (e.g., Weapon, Armor, Shield, etc). If not, explain why. Respond in JSON: {{ "allowed": true/false, "slot": "SlotName" or null, "reason": "short explanation" }}. Only output valid JSON."
    """
    response = await get_llm_response(prompt, ollama_host, ollama_model)
    import json
    try:
        return json.loads(response)
    except Exception:
        return {"allowed": False, "slot": None, "reason": "LLM response could not be parsed."}

# State-specific LLM prompts for the Discord bot state engine
SESSION_ZERO_QA_PROMPT = (
    "You are the DM. Answer the player's question as a helpful guide about the campaign world, setting, or rules. "
    "Do NOT narrate the current in-game situation, location, or events. Only provide information about the world, lore, rules, or character options. "
    "If the question is about the story so far, say that the adventure hasn't started yet.\n\n"
    "Campaign Info:\n{context}\n\nPlayer Question:\n{player_input}"
)

CAMPAIGN_STARTED_PROMPT = (
    "You are the DM. The campaign has started, but no adventure is running yet. "
    "Players may shop, explore the town, interact with NPCs, or prepare for the adventure. "
    "Answer as the DM, roleplaying shopkeepers, describing shops, prices, and available items, or responding to downtime activities. "
    "Do NOT start the adventure or narrate story events.\n\n"
    "Campaign Info:\n{context}\n\nPlayer Message:\n{player_input}"
)

ADVENTURE_RUNNING_PROMPT = (
    "You are the DM. The adventure is currently running. "
    "Describe the world, NPCs, and outcomes of player actions. "
    "Do NOT make decisions for the players.\n\n"
    "Adventure Info:\n{context}\n\nPlayer Message:\n{player_input}"
)

# Add more prompts as needed for other states