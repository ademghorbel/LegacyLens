"""Quick check that GOOGLE_API_KEY works (one tiny Gemini call)."""
import os, time
from dotenv import load_dotenv
load_dotenv(".env")
from langchain_google_genai import ChatGoogleGenerativeAI

t = time.time()
try:
    r = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"), timeout=int(os.getenv("LLM_TIMEOUT", "30")), max_retries=1).invoke("Reply with the word OK only.")
    print("OK:", repr(r.content)[:50], f"{time.time() - t:.1f}s")
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:400])
