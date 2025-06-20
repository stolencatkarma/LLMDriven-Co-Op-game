import random

# --- Basic d20 Ruleset (Distilled) ---

def roll_3d6():
    """Roll 3d6 and return the sum."""
    return sum(random.randint(1, 6) for _ in range(3))

def roll_4d6k3():
    """Roll 4d6, drop the lowest, and return the sum of the highest 3."""
    rolls = [random.randint(1, 6) for _ in range(4)]
    return sum(sorted(rolls)[1:])

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

STARTING_INVENTORY = {
    # Example: (race, class): [items]
    ("Human", "Fighter"): ["Longsword", "Shield", "Chainmail", "Rations"],
    ("Elf", "Wizard"): ["Quarterstaff", "Spellbook", "Robes", "Rations"],
    ("Dwarf", "Cleric"): ["Warhammer", "Chainmail", "Holy Symbol", "Rations"],
    ("Halfling", "Rogue"): ["Dagger", "Leather Armor", "Thieves' Tools", "Rations"],
    # Add more as needed
}

def generate_ability_scores():
    """Generate ability scores using 4d6k3 for each ability."""
    abilities = {}
    for ability in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        abilities[ability] = roll_4d6k3()
    return abilities

class Character:
    def __init__(self, name, race, char_class, abilities=None, skills=None, advantages=None, powers=None, pp=20, inventory=None, backstory=None, equipped=None):
        """
        abilities: dict of ability modifiers, e.g. {'STR': 2, 'DEX': 1, ...}
        skills: dict of skill ranks, e.g. {'Athletics': 1, ...}
        advantages: list of feats/class abilities
        powers: list of powers
        pp: Power Points available
        inventory: list of items carried
        equipped: dict mapping slot (e.g., 'Weapon', 'Armor') to item name
        """
        self.name = name
        self.race = race
        self.char_class = char_class
        self.abilities = abilities or generate_ability_scores()
        self.skills = skills or {skill: 0 for skill, _ in BROAD_SKILLS}
        self.advantages = advantages or []
        self.powers = powers or []
        self.pp = pp
        self.inventory = inventory or self.get_starting_inventory()
        self.backstory = backstory or ""
        self.equipped = equipped or {}  # e.g., {'Weapon': 'Longsword', 'Armor': 'Chainmail'}

    def get_starting_inventory(self):
        return STARTING_INVENTORY.get((self.race, self.char_class), ["Rations", "Backpack"])

    def equip_item(self, item, slot):
        """Equip an item from inventory to a slot (e.g., 'Weapon', 'Armor')."""
        if item not in self.inventory:
            raise ValueError(f"Item '{item}' not in inventory.")
        self.equipped[slot] = item

    def unequip_item(self, slot):
        """Unequip an item from a slot."""
        if slot in self.equipped:
            del self.equipped[slot]

    def is_equipped(self, item):
        """Check if an item is currently equipped."""
        return item in self.equipped.values()

    def get_equipped(self, slot):
        """Get the item equipped in a given slot, or None."""
        return self.equipped.get(slot)

    def list_equipped(self):
        """
        Return equipped items as a dict.
        """
        return dict(self.equipped)

    def list_inventory(self):
        """
        Return inventory as a list.
        """
        return list(self.inventory)

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
# char = Character("Alice", "Human", "Fighter")
# result = char.skill_check('Athletics', dc=15)
# print(result)
