def update_world_state_from_room(world_state, room_data):
    world_state["description"] = room_data.get("description", world_state["description"])
    world_state["image"] = room_data.get("image")
