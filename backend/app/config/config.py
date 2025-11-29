import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    CORS_URLS = os.getenv("CORS_URLS", "*")