# src/agent/nodes/fortran_node/summarizers/human_summarizer.py

from pathlib import Path

from ..config import FORTRAN_SUMMARIZER_CONFIG
from ..utils import call_llm

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
    return call_llm(
        prompt,
        system="You are a helpful assistant who summarizes legacy code for non-developers.",
        temperature=FORTRAN_SUMMARIZER_CONFIG["temperature"],
    )
