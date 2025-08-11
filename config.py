import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- BOT ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS_str.split(",") if admin_id]
YOUR_USERNAME = os.getenv("YOUR_USERNAME", "your_telegram_username")

# --- DATABASE ---
DB_FILE = os.getenv("DB_FILE", "bot_data.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE}"

# --- PAGING ---
USERS_PER_PAGE = 5

# --- APIS ---
# Google Cloud
PROJECT_ID = os.getenv("PROJECT_ID")
ENDPOINT_ID = os.getenv("ENDPOINT_ID")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "key.json")
LOCATION = "us-central1"
MODEL_ID_PRO = "gemini-2.0-flash"

# A simple check to enable/disable API features based on presence of credentials
API_ENABLED = bool(PROJECT_ID and ENDPOINT_ID and SERVICE_ACCOUNT_FILE)


# News API
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Price API
PRICE_API_URL = os.getenv("PRICE_API_URL", "https://abalahb.cfd/forex")

# Economic Calendar
ECONOMIC_CALENDAR_URL = "https://www.myfxbook.com/forex-economic-calendar"
ECONOMIC_CALENDAR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
