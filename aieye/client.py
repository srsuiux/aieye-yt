import os
from .ui import fail

# OPENAI CLIENT

def get_client():
    try:
        from openai import OpenAI
    except ImportError:
        fail("pip install openai")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        fail("OPENAI_API_KEY not set in .env or environment")
    return OpenAI(api_key=key)

