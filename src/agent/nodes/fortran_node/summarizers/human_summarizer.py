# src/agent/nodes/fortran_node/summarizers/human_summarizer.py

import os
from pathlib import Path
import openai

from ..config import FORTRAN_SUMMARIZER_CONFIG

# Set OpenRouter credentials from config
openai.api_key = os.getenv(FORTRAN_SUMMARIZER_CONFIG["api_key_env"])
openai.api_base = FORTRAN_SUMMARIZER_CONFIG["api_base"]

# Path to the human prompt template
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "fortran_human.txt"

def load_prompt(filepath: Path, code: str) -> str:
    """
    Load a prompt template and inject the code into it.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("{code}", code)

def generate_human_summary(code: str) -> str:
    """
    Generate a human-readable summary of the Fortran code using DeepSeek API.
    """
    prompt = load_prompt(PROMPT_PATH, code)

    response = openai.ChatCompletion.create(
        model=FORTRAN_SUMMARIZER_CONFIG["model"],
        messages=[
            {"role": "system", "content": "You are a helpful assistant who summarizes legacy code for non-developers."},
            {"role": "user", "content": prompt}
        ],
        temperature=FORTRAN_SUMMARIZER_CONFIG["temperature"],
        max_tokens=FORTRAN_SUMMARIZER_CONFIG["max_tokens"]
    )

    return response['choices'][0]['message']['content'].strip()
