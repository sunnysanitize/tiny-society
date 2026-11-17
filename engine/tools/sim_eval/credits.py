"""Print remaining OpenRouter credit (usage tracking between eval rounds)."""
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
r = httpx.get("https://openrouter.ai/api/v1/credits",
              headers={"Authorization": f"Bearer {os.environ['OPENAI_COMPAT_API_KEY']}"}, timeout=30)
d = r.json()["data"]
print(f"{d['total_credits'] - d['total_usage']:.2f}")
