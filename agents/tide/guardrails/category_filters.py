"""Charter-as-code: Policy Part C2.

Every candidate product passes through here before it can be scored or picked.
EXCLUDED  -> never scored, never shown as a pick.
FLAGGED   -> scored, but shown with a plain-language warning the UI must display.

These lists are deliberately conservative. Loosening them requires a written
founder exception per Policy Part G. Do not "optimize" them away.
"""

EXCLUDE = {
    "weapons": [
        "knife", "knives", "gun", "firearm", "ammo", "taser", "pepper spray",
        "brass knuckle", "crossbow", "sword",
    ],
    "ingestible_or_supplement": [
        "supplement", "vitamin", "gummies", "protein powder", "detox", "tea cleanse",
        "appetite", "fat burner", "nootropic", "melatonin",
    ],
    "medical_claims_device": [
        "cure", "treatment", "therapy device", "tens unit", "blood pressure",
        "glucose", "medical",
    ],
    "counterfeit_ip_risk": [
        "nike", "adidas", "disney", "marvel", "pokemon", "lego", "gucci",
        "louis vuitton", "nfl", "nba", "jordan", "apple airpods", "dyson",
    ],
    "adult_or_age_restricted": ["vape", "nicotine", "cbd", "thc", "alcohol"],
}

FLAG = {
    "children_products": [
        "baby", "infant", "toddler", "kids toy", "children", "crib", "pacifier",
    ],
    "battery_or_mains_electrical": [
        "lithium", "battery pack", "charger", "power bank", "heater", "plug-in",
        "corded", "usb-c hub", "e-bike", "scooter",
    ],
    "skin_applied_cosmetic": [
        "serum", "cream", "skincare", "led mask", "teeth whitening", "lash",
        "hair growth", "essential oil",
    ],
    "eu_gpsr_generic": [],  # applied at listing time for EU sellers, not by keyword
}


def check(product_name: str) -> tuple[str, list[str]]:
    """Return (status, reasons). status in {'clear','flagged','excluded'}."""
    name = f" {product_name.lower()} "
    reasons: list[str] = []

    for reason, words in EXCLUDE.items():
        if any(w in name for w in words):
            reasons.append(f"excluded:{reason}")
    if reasons:
        return "excluded", reasons

    for reason, words in FLAG.items():
        if any(w in name for w in words):
            reasons.append(f"flagged:{reason}")
    if reasons:
        return "flagged", reasons

    return "clear", []


def human_warning(reasons: list[str]) -> str:
    """Plain-language warning text (idiot-proof UI rule: no jargon)."""
    mapping = {
        "flagged:children_products":
            "This is a children's product. Safety rules are strict and penalties "
            "are serious. Only sell it if you understand CPSIA/GPSR requirements.",
        "flagged:battery_or_mains_electrical":
            "This plugs in or contains batteries. Fire risk means higher liability "
            "and shipping restrictions. Choose suppliers with real certifications.",
        "flagged:skin_applied_cosmetic":
            "This goes on skin. Never make health claims in ads, and vet the "
            "supplier's ingredient documentation.",
    }
    return " ".join(mapping.get(r, "") for r in reasons).strip()
