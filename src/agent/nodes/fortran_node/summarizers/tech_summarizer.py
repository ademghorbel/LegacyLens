# src/agent/nodes/fortran_node/summarizers/tech_summarizer.py

from pathlib import Path

from ..config import TECHNICAL_SUMMARIZER_CONFIG
from ..utils import call_llm

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
    return call_llm(
        prompt,
        system="You are a senior Fortran developer tasked with explaining legacy code to technical engineers.",
        temperature=TECHNICAL_SUMMARIZER_CONFIG["temperature"],
    )
