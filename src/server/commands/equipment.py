async def equipment_command(message, characters, **kwargs):
    user_id = str(message.author.id)
    char = characters.get(user_id)
    if not char:
        await message.channel.send("Character not found.")
        return
    equipped = char.list_equipped()
    inventory = char.list_inventory()
    eq_lines = [f"**Equipped Items:**"]
    if equipped:
        for slot, item in equipped.items():
            eq_lines.append(f"- {slot}: {item}")
    else:
        eq_lines.append("(None equipped)")
    eq_lines.append("\n**Inventory:**")
    if inventory:
        for item in inventory:
            eq_lines.append(f"- {item}{' (equipped)' if char.is_equipped(item) else ''}")
    else:
        eq_lines.append("(Empty)")
    await message.channel.send("\n".join(eq_lines))
