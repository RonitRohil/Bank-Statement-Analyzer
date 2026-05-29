import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    CORS_URLS = os.getenv("CORS_URLS", "http://localhost:3000")
    INTEGRATION_URL = os.getenv("INTEGRATION_URL", "")
    INTEGRATION_AUTH = os.getenv("INTEGRATION_AUTH", "")
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))  # 20 MB default
