"""
LegacyLens API — FastAPI wrapper over the LangGraph pipeline.

Run: uvicorn api.main:app --reload
"""

import sys
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="LegacyLens API", version="0.1.0")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AnalyseRequest(BaseModel):
    project_path: Optional[str] = None
    github_url: Optional[str] = None
    branch: Optional[str] = None
    max_files: int = 20
    include_tests: bool = False


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    analysis_results: Dict[str, Any]
    history: List[ChatMessage] = []


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/analyse")
async def analyse(req: AnalyseRequest):
    if bool(req.project_path) == bool(req.github_url):
        raise HTTPException(400, "Provide exactly one of project_path or github_url")
    if req.project_path and not Path(req.project_path).is_dir():
        raise HTTPException(400, f"project_path not found: {req.project_path}")

    if req.github_url:
        from github_integration.github_analyzer import GitHubAnalyzer
        analyzer = GitHubAnalyzer(os.getenv("GITHUB_TOKEN"))
        try:
            return await analyzer.analyze_github_repository(
                github_url=req.github_url,
                branch=req.branch,
                max_files=req.max_files,
                include_tests=req.include_tests,
                verbose_mode=False,
            )
        except ValueError as e:  # bad URL, repo not found, no access
            raise HTTPException(400, f"Could not clone repository: {e}")
        except Exception as e:
            raise HTTPException(502, f"GitHub analysis failed: {type(e).__name__}: {str(e)[:300]}")
        finally:
            try:
                analyzer.cleanup()
            except Exception:
                pass

    from agent.graph import create_graph, State
    graph = create_graph()
    initial_state = State(
        project_path=req.project_path,
        analysis_complete=False,
        files_to_process_with_cobol=[],
        files_to_process_with_vb6=[],
        files_to_process_with_fortran=[],
        files_to_process_with_generic=[],
        detected_languages=[],
        detected_frameworks=[],
        cobol_results=[],
        vb6_results=[],
        fortran_results=[],
        generic_results=[],
        functionality_analyses=[],
    )
    config = {"configurable": {
        "project_path": req.project_path,
        "max_files": req.max_files,
        "include_tests": req.include_tests,
        "verbose": False,
    }}
    return await graph.ainvoke(initial_state, config)


@app.post("/chat")
async def chat(req: ChatRequest):
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    from agent.llm import ainvoke, classify_error, get_llm

    # Build context inline (same logic as Streamlit helper)
    results = req.analysis_results
    lines = []
    for lang in results.get("detected_languages", []):
        lines.append(f"Language: {lang}")
    for a in results.get("functionality_analyses", [])[:30]:
        fname = a.get("filename") or Path(a.get("file_path", "?")).name
        lines.append(f"\n[{fname} | {a.get('language', '?')}]")
        for f in a.get("functionalities", [])[:5]:
            lines.append(f"  - {f}")
    context = "\n".join(lines) or "No analysis data."

    llm = get_llm(temperature=0.3, timeout=90)
    messages = [SystemMessage(content=(
        "You are an expert software architect specialising in legacy system modernisation. "
        f"Codebase analysis:\n\n{context}\n\nBe concise and actionable."
    ))]
    for m in req.history:
        if m.role == "user":
            messages.append(HumanMessage(content=m.content))
        else:
            messages.append(AIMessage(content=m.content))
    messages.append(HumanMessage(content=req.message))

    try:
        return {"reply": await ainvoke(llm, messages)}
    except Exception as e:
        kind, status = classify_error(e)
        raise HTTPException(status_code=status, detail=f"LLM {kind}: {type(e).__name__}: {str(e)[:300]}")


@app.get("/health")
def health():
    return {"status": "ok"}
