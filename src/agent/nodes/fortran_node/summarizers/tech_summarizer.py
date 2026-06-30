# src/agent/nodes/fortran_node/summarizers/tech_summarizer.py

import os
from pathlib import Path
import openai

from ..config import TECHNICAL_SUMMARIZER_CONFIG

# Set OpenRouter credentials from config
openai.api_key = os.getenv(TECHNICAL_SUMMARIZER_CONFIG["api_key_env"])
openai.api_base = TECHNICAL_SUMMARIZER_CONFIG["api_base"]

# Path to the technical prompt template
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "fortran_tech.txt"

def load_prompt(filepath: Path, code: str) -> str:
    """
    Load a technical prompt template and inject the code into it.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Prompt file not found: {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("{code}", code)

def generate_technical_summary(code: str) -> str:
    """
    Generate a technical summary of the Fortran code using DeepSeek API.
    """
    prompt = load_prompt(PROMPT_PATH, code)

    response = openai.ChatCompletion.create(
        model=TECHNICAL_SUMMARIZER_CONFIG["model"],
        messages=[
            {"role": "system", "content": "You are a senior Fortran developer tasked with explaining legacy code to technical engineers."},
            {"role": "user", "content": prompt}
        ],
        temperature=TECHNICAL_SUMMARIZER_CONFIG["temperature"],
        max_tokens=TECHNICAL_SUMMARIZER_CONFIG["max_tokens"]
    )

    return response['choices'][0]['message']['content'].strip()
