import json
from pathlib import Path

async def sell_command(message, args, characters, save_characters, ollama_host, ollama_model, **kwargs):
    if not args:
        await message.channel.send("Usage: !sell <item name>")
        return
    item_name = ' '.join(args)
    user_id = str(message.author.id)
    char = characters.get(user_id)
    if not char:
        await message.channel.send("Character not found.")
        return
    # Load shop items
    gear_path = Path(__file__).parent.parent / "gear" / "gear.json"
    with open(gear_path, "r", encoding="utf-8") as f:
        shop_items = json.load(f)
    item = next((i for i in shop_items if i["name"].lower() == item_name.lower()), None)
    if not item:
        await message.channel.send(f"Item '{item_name}' not found in shop.")
        return
    # Check if player owns the item
    if hasattr(char, "inventory"):
        if item["name"] not in char.inventory:
            await message.channel.send(f"You do not own {item['name']}.")
            return
        char.inventory.remove(item["name"])
    else:
        if item["name"] not in char["inventory"]:
            await message.channel.send(f"You do not own {item['name']}.")
            return
        char["inventory"].remove(item["name"])
    # Refund half price (rounded down)
    price = item.get("price", 0)
    refund = price // 2
    if getattr(char, "pp", None) is None:
        char.pp = 20  # Default if missing
    char.pp += refund
    save_characters(characters)
    # --- AUTO-SAVE CAMPAIGN STATE if available ---
    campaign = None
    if 'save_campaign_state' in kwargs and 'load_campaign_state' in kwargs:
        load_campaign_state = kwargs['load_campaign_state']
        save_campaign_state = kwargs['save_campaign_state']
        campaign = load_campaign_state()
        if campaign:
            campaign['characters'] = characters
            save_campaign_state(campaign)
    await message.channel.send(f"{message.author.display_name} sold {item['name']} for {refund} PP.")
