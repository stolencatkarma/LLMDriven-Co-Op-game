def detect_movement(content, current_location, get_room):
    import re
    current_room = get_room(current_location)
    exits = current_room.get("exits", []) if current_room else []
    for exit_name in exits:
        if exit_name.lower() in content.lower():
            return exit_name
    match = re.search(r"\bgo (\w+)\b", content.lower())
    return match.group(1).capitalize() if match else None
