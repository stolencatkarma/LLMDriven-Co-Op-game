async def players_command(message, characters, **kwargs):
    if not characters:
        await message.channel.send("No active players yet.")
        return
    player_lines = ["**Active Players:**"]
    for user_id, char in characters.items():
        name = char.get('name') or getattr(char, 'name', None) or f"User {user_id}"
        race_class = char.get('race_class') or f"{getattr(char, 'race', '')} {getattr(char, 'char_class', '')}".strip()
        player_lines.append(f"- {name} ({race_class})")
    await message.channel.send("\n".join(player_lines))
