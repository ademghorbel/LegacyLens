"""Run the full pipeline on a folder and print a short report.

Usage: python scripts/run_pipeline.py [project_path]   (default: examples/demo_project)
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from agent.graph import State, create_graph  # noqa: E402


async def main(project: str) -> int:
    start = time.monotonic()
    result = await create_graph().ainvoke(State(project_path=project), {"recursion_limit": 500})
    elapsed = time.monotonic() - start

    print("\n" + "=" * 70)
    print(f"Project: {project}   ({elapsed:.0f}s)")
    print(f"Languages: {result['detected_languages']}   Frameworks: {result['detected_frameworks']}")
    failed = 0
    for a in result["functionality_analyses"]:
        ok = a["processing_status"] == "completed"
        failed += not ok
        print(f"\n[{'OK ' if ok else 'ERR'}] {a['filename']} ({a['language']}, {a['node_type']})")
        for f in a["functionalities"][:4]:
            print(f"      - {str(f)[:110]}")
    if failed:
        print("\nErrors:")
        for p in result["processed_files"]:
            if p.get("processing_status") != "completed":
                print(f"  {Path(p['file_path']).name}: {str(p.get('message'))[:250]}")
    print(f"\nAggregation: {result['aggregation_status']}")
    for m in result["modules"]:
        print(f"  * {m.get('module_name')}: {len(m.get('endpoints', []))} endpoints, "
              f"{len(m.get('entities', {}))} entities, stack {m.get('tech_stack')}")
    out = ROOT / "outputs" / "last_run.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nFull state saved to {out.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "examples" / "demo_project")
    sys.exit(asyncio.run(main(target)))
