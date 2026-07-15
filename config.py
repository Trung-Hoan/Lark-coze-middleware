import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Lark Global
    LARK_APP_ID = os.getenv("LARK_APP_ID")
    LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
    LARK_VERIFICATION_TOKEN = os.getenv("LARK_VERIFICATION_TOKEN")
    LARK_ENCRYPT_KEY = os.getenv("LARK_ENCRYPT_KEY", "")
    LARK_BOT_NAME = os.getenv("LARK_BOT_NAME", "Da VinCi")

    # Coze.cn
    COZE_TOKEN = os.getenv("COZE_TOKEN")
    COZE_BOT_ID = os.getenv("COZE_BOT_ID")
    COZE_BASE_URL = os.getenv("COZE_BASE_URL", "https://api.coze.cn")
    COZE_API_VERSION = os.getenv("COZE_API_VERSION", "v3")

    # App
    DATABASE_PATH = os.getenv("DATABASE_PATH", "lark_coze.db")
    FALLBACK_MESSAGE = os.getenv(
        "FALLBACK_MESSAGE",
        "Xin lỗi, tôi đang gặp lỗi. Vui lòng thử lại sau."
    )
    WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

settings = Settings()
