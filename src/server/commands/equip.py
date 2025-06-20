from llm_utils import llm_can_equip

async def equip_command(message, args, characters, save_characters, ollama_host, ollama_model, **kwargs):
    if not args:
        await message.channel.send("Usage: !equip <item or phrase>")
        return
    item_phrase = ' '.join(args)
    user_id = str(message.author.id)
    char = characters.get(user_id)
    if not char:
        await message.channel.send("Character not found.")
        return
    # Call LLM to adjudicate equip request
    equip_result = await llm_can_equip(char, item_phrase, ollama_host, ollama_model)
    if equip_result.get('allowed'):
        slot = equip_result.get('slot') or 'Misc'
        try:
            char.equip_item(item_phrase, slot)
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
            await message.channel.send(f"{message.author.display_name} equipped {item_phrase} in {slot} slot.")
        except Exception as e:
            await message.channel.send(f"Could not equip: {e}")
    else:
        await message.channel.send(f"Cannot equip '{item_phrase}': {equip_result.get('reason','Not allowed.')}")
