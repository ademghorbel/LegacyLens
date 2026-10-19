"""List Gemini models available to this API key that support text generation."""
import os
from dotenv import load_dotenv
load_dotenv(".env")
from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
for m in client.models.list():
    if "generateContent" in (m.supported_actions or []):
        print(m.name, "| in", m.input_token_limit, "| out", m.output_token_limit)
