async def send_dm_response(channel, raw_message, exits, world_state, replace_mentions):
    import re
    from discord import File
    from pathlib import Path
    clean_message = re.sub(r"", "", raw_message, flags=re.DOTALL).strip()
    reply = f"**DM:** {replace_mentions(clean_message, channel)}"
    if exits:
        reply += f"\n\n**Exits:** {', '.join(exits)}"
    else:
        reply += "\n\n**Exits:** None"
    image_path = world_state.get("image")
    if image_path and Path(image_path).exists():
        with open(image_path, "rb") as img_fp:
            await channel.send(file=File(img_fp, Path(image_path).name))
    await channel.send(reply)
