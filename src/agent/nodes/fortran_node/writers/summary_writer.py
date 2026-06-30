# src/agent/nodes/fortran_node/writers/summary_writer.py

import json
from pathlib import Path
from typing import Dict


def get_output_dir(file_path: str) -> Path:
    """Create and return output directory based on source file name."""
    file_stem = Path(file_path).stem
    output_dir = Path("outputs") / "fortran" / file_stem
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_txt(path: Path, content: str):
    """Write content to a .txt file."""
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: Dict):
    """Write dictionary as JSON file."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_summaries(base_path: str, human_summary: str, tech_summary: str, functionality_summary: Dict) -> Dict[str, str]:
    """
    Save all summaries (human, tech, json) to disk.
    Returns paths of saved files.
    """

    output_dir = get_output_dir(base_path)

    # File paths
    human_path = output_dir / "fortran_human.txt"
    tech_path = output_dir / "fortran_tech.txt"
    json_path = output_dir / "fortran_summary.json"

    # Write files
    write_txt(human_path, human_summary)
    write_txt(tech_path, tech_summary)
    write_json(json_path, functionality_summary)

    return {
        "human_summary_path": str(human_path),
        "tech_summary_path": str(tech_path),
        "json_summary_path": str(json_path),
    }
