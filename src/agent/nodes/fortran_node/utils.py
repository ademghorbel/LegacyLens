# src/agent/nodes/fortran_node/utils.py

from pathlib import Path
from typing import Dict, Optional
import openai
import re
import os


def read_file_content(file_path: str, encoding: str = "utf-8") -> str:
    """Reads the contents of a file with the given encoding."""
    return Path(file_path).read_text(encoding=encoding)

def extract_file_info(file_info: Dict[str, str]) -> Dict[str, str]:
    """Safely extracts file_path, filename, and language from file_info."""
    return {
        "file_path": file_info.get("file_path", ""),
        "filename": file_info.get("filename", ""),
        "language": file_info.get("language", "fortran")
    }

def print_log(message: str, emoji: str = "ℹ️") -> None:
    """Standard log printer with emoji."""
    print(f"  {emoji} {message}")


def clean_llm_output(summary: str) -> str:
    """
    Removes typical LLM follow-up questions or suggestions from the summary.
    """
    # Simple heuristic: Remove any lines that end in a question mark or contain known LLM phrases
    lines = summary.strip().splitlines()
    cleaned = []
    for line in lines:
        if re.search(r"(do you want|would you like|need more|can also provide|example\?)", line, re.IGNORECASE):
            continue
        if line.strip().endswith("?"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def call_openrouter(prompt: str, config: dict) -> str:
    openai.api_key = os.getenv(config.get("api_key_env", "OPENROUTER_API_KEY"))
    openai.api_base = config.get("api_base", "https://openrouter.ai/api/v1")

    response = openai.ChatCompletion.create(
        model=config["model"],  # ✅ Correct usage
        messages=[
            {"role": "system", "content": "You are a helpful assistant that describes the purpose of Fortran code."},
            {"role": "user", "content": prompt}
        ],
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 500),
    )
    return response["choices"][0]["message"]["content"].strip()
