# Add missing import
import string

# Fix the generate_bot_username function
def generate_bot_username() -> str:
    """Generate obvious bot username patterns"""
    patterns = [
        f"user{random.randint(100000, 999999)}",
        "".join(random.choices(string.digits, k=10)),
        f"bot_{random.randint(1000, 9999)}_account",
        "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    ]
    return random.choice(patterns)
