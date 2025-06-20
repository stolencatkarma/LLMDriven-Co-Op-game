async def move_command(message, args, handle_movement, world_state, **kwargs):
    if not args:
        await message.channel.send("Usage: !move <destination>")
        return
    destination = ' '.join(args)
    await handle_movement(message, destination, world_state["location"], via_command=True)
