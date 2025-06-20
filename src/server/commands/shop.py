import json
from pathlib import Path

async def shop_command(message, **kwargs):
    gear_path = Path(__file__).parent.parent / "gear" / "gear.json"
    with open(gear_path, "r", encoding="utf-8") as f:
        shop_items = json.load(f)
    lines = ["**Shop Items:**"]
    for item in shop_items:
        name = item.get("name", "Unknown")
        price = item.get("price", 0)
        desc = item.get("description", "")
        lines.append(f"- {name} ({price} PP): {desc}")
    await message.channel.send("\n".join(lines))
