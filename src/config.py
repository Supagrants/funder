import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_project_root() -> Path:
    return Path(__file__).parent.parent


ENVIRONMENT = os.getenv("ENVIRONMENT", "")

MONGO_SERVER = os.getenv("MONGO_SERVER", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_CONNECTION = os.getenv("MONGO_CONNECTION", None)
MONGO_DB = 'supagrants'

POSTGRES_CONNECTION = os.getenv("POSTGRES_CONNECTION", "postgresql+psycopg://ai:ai@localhost:5532/ai")

TELEGRAM_BOT = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_BOT_ID = os.getenv("TELEGRAM_BOT_ID", "")  # todo
TELEGRAM_BOT_HANDLE = os.getenv("TELEGRAM_BOT_HANDLE", "@supgrantsBot")

# PagerDuty & Support
PAGERDUTY_INACTIVE = os.getenv("PAGERDUTY_INACTIVE", 0)
PAGERDUTY = os.getenv("PAGERDUTY", "")

# AI
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# Crawler
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
GITHUB_ACCESS_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN", "")

# Chat
TOKEN_LIMIT = int(os.getenv("TOKEN_LIMIT", 28000))
TOOL_MESSAGE_CHAR_TRUNCATE_LIMIT = int(os.getenv("TOOL_MESSAGE_CHAR_TRUNCATE_LIMIT", 400))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", 50))