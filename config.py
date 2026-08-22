import os
from pathlib import Path
from typing import List, Set
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Bot Settings
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs
_admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: Set[int] = set()
if _admin_ids_raw:
    for raw_id in _admin_ids_raw.split(","):
        clean_id = raw_id.strip()
        if clean_id.isdigit():
            ADMIN_IDS.add(int(clean_id))

# Support and Social
SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "@AdminSupport").strip()
CHANNEL_USERNAME: str = os.getenv("CHANNEL_USERNAME", "@StoreChannel").strip()

# Database
DB_PATH: str = os.getenv("DB_PATH", "data/store.db").strip()
DB_FILE = BASE_DIR / DB_PATH
MONGO_URI: str = os.getenv("MONGO_URI", "").strip()

# Paytm & UPI QR Settings
PAYTM_UPI_ID: str = os.getenv("PAYTM_UPI_ID", "store@paytm").strip()
PAYTM_MERCHANT_NAME: str = os.getenv("PAYTM_MERCHANT_NAME", "Digital Store").strip()
PAYTM_MERCHANT_ID: str = os.getenv("PAYTM_MERCHANT_ID", "").strip()

# Paytm Session Cookies for Auto-verification
PAYTM_SESSION: str = os.getenv("PAYTM_SESSION", "").strip()
PAYTM_XSRF_TOKEN: str = os.getenv("PAYTM_XSRF_TOKEN", "").strip()
PAYTM_UMP_SESSION: str = os.getenv("PAYTM_UMP_SESSION", "").strip()
PAYTM_ABCK: str = os.getenv("PAYTM_ABCK", "").strip()
PAYTM_AK_BMSC: str = os.getenv("PAYTM_AK_BMSC", "").strip()
PAYTM_BM_SZ: str = os.getenv("PAYTM_BM_SZ", "").strip()

# Auto Verification Polling Interval (seconds)
AUTO_VERIFY_INTERVAL: int = int(os.getenv("AUTO_VERIFY_INTERVAL", "15"))

# Store Settings
MIN_DEPOSIT: float = float(os.getenv("MIN_DEPOSIT", "10"))
REFERRAL_PERCENT: float = float(os.getenv("REFERRAL_PERCENT", "5.0"))

def is_admin(user_id: int) -> bool:
    """Check if a given user ID is an admin"""
    return user_id in ADMIN_IDS

def add_admin(user_id: int):
    """Add an admin dynamically"""
    ADMIN_IDS.add(user_id)
