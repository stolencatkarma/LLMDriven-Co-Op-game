async def help_command(message, **kwargs):
    help_text = """
**Available Commands:**
!roll <dice or skill> - Roll dice or make a skill check
!move <destination> - Move to a new room/location
!equip <item> - Equip an item from your inventory
!equipment - List your equipped items and inventory
!players - List all active players
!buy <item> - Buy an item from the shop
!sell <item> - Sell an item from your inventory
!shop - List all available shop items
!help - Show this help message
"""
    await message.channel.send(help_text)
