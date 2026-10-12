"""
settings.py — load local secrets from the project's .env file.
The .env file is git-ignored; it holds e.g.  OPENAI_API_KEY=sk-...
A variable already set in the environment always wins over the file.
"""
import os

HERE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(HERE, ".env")

def load_env(path=ENV_FILE):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
