def replace_mentions(text, channel, get_user_mention):
    if not hasattr(channel, "guild"):
        return text
    import re
    return re.sub(
        r"@(\d{17,20})",
        lambda m: get_user_mention(m.group(1), channel.guild),
        text
    )

def get_user_mention(user, guild):
    user_id = getattr(user, "id", None) or user
    if guild is None:
        return f"<@{user_id}>"
    member = guild.get_member(int(user_id))
    if member:
        return member.mention
    return f"<@{user_id}>"
