# src/agent/nodes/fortran_node/utils.py

from pathlib import Path
from typing import Dict, Optional
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


def call_llm(prompt: str, system: str = "You are a helpful assistant that describes the purpose of Fortran code.",
             temperature: float = 0.3) -> str:
    """Single LLM entry point for the Fortran node.

    ponytail: original code used OpenRouter via the legacy openai.ChatCompletion API
    (removed in openai>=1.0). The rest of the pipeline runs on Gemini — use the same.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temperature)
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
    return response.content.strip()


def call_openrouter(prompt: str, config: dict) -> str:
    """Legacy name kept for existing callers — now routed through Gemini."""
    return call_llm(prompt, temperature=config.get("temperature", 0.3))
