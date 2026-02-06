import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.environ.get("DATABASE_URL")

# Mock mode (for testing without API key)
MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"

# OpenAI
OPENAI_MODEL = "gpt-5.2"

# Stripe
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_UNLOCK = os.environ.get("STRIPE_PRICE_UNLOCK", "price_unlock_3usd")

def get_api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key:
                        return key
    home_config = Path.home() / ".openai" / "api_key"
    if home_config.exists():
        return home_config.read_text().strip()
    return None
