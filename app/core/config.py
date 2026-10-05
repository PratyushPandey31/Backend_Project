import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Detect if running on Vercel
IS_VERCEL = os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV") is not None

class Settings(BaseModel):
    PROJECT_NAME: str = "AI Real Estate Portfolio Analyst"
    # On Vercel, use /tmp (ephemeral writable dir). Locally use ./portfolio.db
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:////tmp/portfolio.db" if IS_VERCEL else "sqlite:///./portfolio.db"
    )
    
    # Model Gateway & API Keys
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Model configuration
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "google/gemini-2.5-flash")
    FAST_MODEL: str = os.getenv("FAST_MODEL", "meta-llama/llama-3.3-70b-instruct")
    FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "openai/gpt-4o-mini")
    
    # Host and port
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()
