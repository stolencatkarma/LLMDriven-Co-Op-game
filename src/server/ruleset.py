import random

# --- Basic d20 Ruleset (Distilled) ---

def roll_3d6():
    """Roll 3d6 and return the sum."""
    return sum(random.randint(1, 6) for _ in range(3))

def ability_modifier(roll):
    """Convert a 3d6 roll to a Basic d20 modifier."""
    if roll <= 1:
        return -5
    elif roll <= 3:
        return -4
    elif roll <= 5:
        return -3
    elif roll <= 7:
        return -2
    elif roll <= 9:
        return -1
    elif roll <= 11:
        return 0
    elif roll <= 13:
        return 1
    elif roll <= 15:
        return 2
    elif roll <= 17:
        return 3
    elif roll <= 19:
        return 4
    else:
        return 5

BROAD_SKILLS = [
    ("Athletics", "DEX"),
    ("Awareness", "WIS"),
    ("Dodge", "DEX"),
    ("Fight", "STR"),
    ("Fortitude", "CON"),
    ("Interaction", "CHA"),
    ("Knowledge", "INT"),
    ("Languages", "INT"),
    ("Parry", "DEX"),
    ("Performance", "CHA"),
    ("Profession", "WIS"),
    ("Reflex", "DEX"),
    ("Science", "INT"),
    ("Shoot", "DEX"),
    ("Technology", "INT"),
    ("Thievery", "DEX"),
    ("Toughness", "CON"),
    ("Vehicles", "DEX"),
    ("Wilderness", "WIS"),
    ("Will", "WIS"),
]

class Character:
    def __init__(self, name, abilities, skills=None, advantages=None, powers=None, pp=20):
        """
        abilities: dict of ability modifiers, e.g. {'STR': 2, 'DEX': 1, ...}
        skills: dict of skill ranks, e.g. {'Athletics': 1, ...}
        advantages: list of feats/class abilities
        powers: list of powers
        pp: Power Points available
        """
        self.name = name
        self.abilities = abilities
        self.skills = skills or {skill: 0 for skill, _ in BROAD_SKILLS}
        self.advantages = advantages or []
        self.powers = powers or []
        self.pp = pp

    def skill_check(self, skill, ability=None, dc=10):
        """
        Roll d20 + ability modifier + skill rank vs DC.
        If ability is None, use default for skill.
        """
        if skill not in self.skills:
            raise ValueError(f"Unknown skill: {skill}")
        if ability is None:
            # Use default ability for skill
            ability = dict(BROAD_SKILLS)[skill]
        mod = self.abilities.get(ability, 0)
        rank = self.skills[skill]
        roll = random.randint(1, 20)
        total = roll + mod + rank
        return {
            "roll": roll,
            "modifier": mod,
            "rank": rank,
            "total": total,
            "success": total >= dc
        }

    # Combat statistics and saves
    def melee_attack_bonus(self, size_mod=0):
        return self.skills["Fight"] + self.abilities.get("STR", 0) + size_mod

    def ranged_attack_bonus(self, size_mod=0, range_penalty=0):
        return self.skills["Shoot"] + self.abilities.get("DEX", 0) + size_mod + range_penalty

    def melee_defense(self, armor_bonus=0, shield_bonus=0, size_mod=0):
        parry = self.skills["Parry"]
        dex = self.abilities.get("DEX", 0)
        return 10 + dex + max(parry, armor_bonus + shield_bonus) + size_mod

    def ranged_defense(self, armor_bonus=0, shield_bonus=0, size_mod=0):
        dodge = self.skills["Dodge"]
        dex = self.abilities.get("DEX", 0)
        return 10 + dex + max(dodge, armor_bonus + shield_bonus) + size_mod

    def hit_points(self, toughness_feats=0):
        toughness = self.skills["Toughness"]
        con = self.abilities.get("CON", 0)
        return toughness * (4 + con) + toughness_feats * 3

    def initiative(self):
        return self.abilities.get("DEX", 0)

    def fortitude_save(self):
        return self.skills["Fortitude"] + self.abilities.get("CON", 0)

    def reflex_save(self):
        return self.skills["Reflex"] + self.abilities.get("DEX", 0)

    def toughness_save(self):
        return self.skills["Toughness"] + self.abilities.get("CON", 0)

    def will_save(self):
        return self.skills["Will"] + self.abilities.get("WIS", 0)

# Example usage:
# char = Character("Alice", {'STR': 2, 'DEX': 1, 'CON': 0, 'INT': -1, 'WIS': 1, 'CHA': 2})
# char.skills['Athletics'] = 1
# result = char.skill_check('Athletics', dc=15)
# print(result)
