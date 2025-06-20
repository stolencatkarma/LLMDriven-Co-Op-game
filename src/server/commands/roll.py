import random

async def roll_command(message, args, **kwargs):
    result = random.randint(1, 20)
    await message.channel.send(f"🎲 {message.author.display_name} rolled a d20: **{result}**")
