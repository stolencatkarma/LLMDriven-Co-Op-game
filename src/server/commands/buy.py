import json
from pathlib import Path

async def buy_command(message, args, characters, save_characters, ollama_host, ollama_model, **kwargs):
    if not args:
        await message.channel.send("Usage: !buy <item name>")
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
    price = item.get("price", 0)
    # Assume Power Points (pp) is currency
    if getattr(char, "pp", None) is None:
        char.pp = 20  # Default if missing
    if char.pp < price:
        await message.channel.send(f"Not enough Power Points (PP). {item['name']} costs {price} PP. You have {char.pp}.")
        return
    # Add item to inventory and deduct PP
    if hasattr(char, "inventory"):
        if item["name"] in char.inventory:
            await message.channel.send(f"You already own {item['name']}.")
            return
        char.inventory.append(item["name"])
    else:
        char["inventory"].append(item["name"])
    char.pp -= price
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
    await message.channel.send(f"{message.author.display_name} bought {item['name']} for {price} PP.")
