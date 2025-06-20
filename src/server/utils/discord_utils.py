def replace_mentions(text, channel, get_user_mention):
    if not hasattr(channel, "guild"):
        return text
    import re
    return re.sub(
        r"@(\d{17,20})",
        lambda m: get_user_mention(m.group(1), channel.guild),
        text
    )

def get_user_mention(user_id, guild):
    user = guild.get_member(int(user_id))
    return f"@{user.display_name}" if user else f"@{user_id}"
