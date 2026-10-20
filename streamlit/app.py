"""
LegacyLens — Streamlit UI
Multi-agent legacy system analyser with interactive chat.
"""

import sys
# ponytail: pipeline code prints emojis; Windows console is CP1252 — force UTF-8 once here
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import os
import streamlit as st
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import zipfile

current_dir = Path(__file__).parent
project_root = current_dir.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

try:
    from agent.graph import create_graph, State
    from agent.orchestrator.orchestrator import orchestrator_node
    from github_integration.github_analyzer import GitHubAnalyzer
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

st.set_page_config(
    page_title="LegacyLens",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; color: #1f77b4; text-align: center; margin-bottom: 1.5rem; }
    .node-card { background:#1a1d23; padding:1rem; border-radius:8px; margin:.8rem 0; border-left:4px solid #1f77b4; }
    .file-item { background:#1a1d23; padding:.5rem; margin:.3rem 0; border-radius:5px; border:1px solid #2e3340; }
    .github-section { background:#1a1d23; padding:1rem; border-radius:8px; border-left:4px solid #24292e; margin:.8rem 0; }
</style>
""", unsafe_allow_html=True)


# ─── Chat helpers ─────────────────────────────────────────────────────────────

def build_chat_context(results: Dict[str, Any]) -> str:
    """Serialise analysis results into a compact LLM context string."""
    lines = []
    langs = results.get("detected_languages", [])
    fws = results.get("detected_frameworks", [])
    if langs:
        lines.append(f"Languages: {', '.join(langs)}")
    if fws:
        lines.append(f"Frameworks: {', '.join(fws)}")

    analyses = results.get("functionality_analyses", [])
    for a in analyses[:30]:  # ponytail: cap at 30 to stay within context
        fname = a.get("filename") or Path(a.get("file_path", "unknown")).name
        lang = a.get("language", "?")
        funcs = a.get("functionalities", [])
        lines.append(f"\n[{fname} | {lang}]")
        for f in funcs[:5]:
            lines.append(f"  - {f}")

    return "\n".join(lines) or "No analysis data available."


def chat_with_context(prompt: str, context: str, history: List[Dict]) -> str:
    """Call Gemini with codebase context + conversation history."""
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    from agent.llm import get_llm, invoke

    llm = get_llm(temperature=0.3, timeout=90)

    system = SystemMessage(content=(
        "You are an expert software architect specialising in legacy system modernisation. "
        "The user has just analysed a codebase. Here is the analysis summary:\n\n"
        f"{context}\n\n"
        "Answer questions about this codebase, suggest modernisation strategies, "
        "identify risks, and propose refactoring plans. Be concise and actionable."
    ))

    messages = [system]
    for m in history[:-1]:  # exclude the current user turn (added before this call)
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        else:
            messages.append(AIMessage(content=m["content"]))
    messages.append(HumanMessage(content=prompt))

    try:
        return invoke(llm, messages)
    except Exception as e:
        from agent.llm import classify_error
        kind, _ = classify_error(e)
        hint = {
            "daily_quota": "The Gemini daily quota is used up. Try again tomorrow or set another GOOGLE_API_KEY.",
            "rate_limited": "Gemini is rate-limiting requests. Wait a minute and ask again.",
            "timeout": "Gemini took too long to answer. Ask again, or raise LLM_TIMEOUT in .env.",
            "auth": "Gemini rejected the API key. Check GOOGLE_API_KEY in .env.",
        }.get(kind, "The LLM call failed.")
        return f"⚠️ {hint}\n\n`{type(e).__name__}: {str(e)[:200]}`"


# ─── Main UI ──────────────────────────────────────────────────────────────────

def main():
    st.markdown('<h1 class="main-header">🔍 LegacyLens</h1>', unsafe_allow_html=True)
    st.caption("Multi-agent legacy system analyser — powered by LangGraph + Gemini")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Configuration")

        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            st.success("✅ GOOGLE_API_KEY set")
        else:
            st.error("❌ GOOGLE_API_KEY missing")
            val = st.text_input("Google API Key:", type="password")
            if val:
                os.environ["GOOGLE_API_KEY"] = val

        st.markdown("---")
        st.header("🔗 GitHub")
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            st.success("✅ GITHUB_TOKEN set")
        else:
            st.info("Optional — for private repos")
            val = st.text_input("GitHub Token:", type="password")
            if val:
                os.environ["GITHUB_TOKEN"] = val

        st.markdown("---")
        st.header("🔧 Options")
        max_files = st.slider("Max files to analyse", 1, 100, 20)
        include_tests = st.checkbox("Include test files", value=False)
        verbose_mode = st.checkbox("Verbose mode", value=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📁 Analyse", "📊 Results", "📈 Stats", "💬 Chat"])

    with tab1:
        analyze_project_tab(max_files, include_tests, verbose_mode)
    with tab2:
        results_tab()
    with tab3:
        statistics_tab()
    with tab4:
        chat_tab()


# ─── Analyse tab ──────────────────────────────────────────────────────────────

def analyze_project_tab(max_files: int, include_tests: bool, verbose_mode: bool):
    st.header("📁 Select project")

    option = st.radio(
        "Input method:",
        ["📂 Local path", "🔗 GitHub URL", "📦 Upload ZIP"],
        horizontal=True,
    )

    project_path = None
    github_url = None
    branch = None

    if option == "📂 Local path":
        project_path = st.text_input("Project path:", placeholder=r"C:\path\to\project")
        if project_path and os.path.exists(project_path):
            st.success(f"✅ Found: {project_path}")
        elif project_path:
            st.error("❌ Path not found")

    elif option == "🔗 GitHub URL":
        github_url = st.text_input("GitHub URL:", placeholder="https://github.com/owner/repo")
        if github_url:
            if not github_url.startswith("https://github.com/"):
                st.error("❌ Must start with https://github.com/")
            else:
                st.success(f"✅ {github_url}")
                branch = st.text_input("Branch (optional):", placeholder="main")

    elif option == "📦 Upload ZIP":
        uploaded = st.file_uploader("Upload ZIP", type=["zip"])
        if uploaded:
            tmp_dir = tempfile.mkdtemp()
            zip_path = Path(tmp_dir) / uploaded.name
            zip_path.write_bytes(uploaded.getbuffer())
            extract_dir = Path(tmp_dir) / "extracted"
            extract_dir.mkdir()
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)
            project_path = str(extract_dir)
            st.success(f"✅ Extracted: {uploaded.name}")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Run analysis", type="primary", width="stretch"):
            if not project_path and not github_url:
                st.error("❌ Select a project first")
                return
            if not os.getenv("GOOGLE_API_KEY"):
                st.error("❌ Google API key required")
                return
            if github_url:
                run_github_analysis(github_url, branch, max_files, include_tests, verbose_mode)
            else:
                run_analysis(project_path, max_files, include_tests, verbose_mode)


def run_github_analysis(github_url, branch, max_files, include_tests, verbose_mode):
    st.header("🔄 Analysing GitHub repo…")
    analyzer = GitHubAnalyzer(os.getenv("GITHUB_TOKEN"))
    try:
        with st.spinner("Cloning repo…"):
            repo_path = analyzer.cloner.clone_repository(github_url, branch or None)
        st.caption(f"Cloned to `{repo_path}`")
        result = _run_graph(repo_path, max_files, include_tests, verbose_mode)
        if result is None:
            return
        result["github_metadata"] = {"github_url": github_url, "branch": branch, "cloned_path": repo_path}
        st.session_state["analysis_results"] = result
        st.session_state["project_path"] = f"GitHub: {github_url}"
        st.session_state["github_metadata"] = result["github_metadata"]
        st.session_state.pop("chat_history", None)  # reset chat for new analysis
        display_results(result)
    except Exception as e:
        st.error(f"❌ {e}")
        if verbose_mode:
            st.exception(e)
    finally:
        try:
            analyzer.cleanup()
        except Exception:
            pass


def run_analysis(project_path, max_files, include_tests, verbose_mode):
    st.header("🔄 Analysing…")
    result = _run_graph(project_path, max_files, include_tests, verbose_mode)
    if result is None:
        return
    st.session_state["analysis_results"] = result
    st.session_state["project_path"] = project_path
    st.session_state.pop("chat_history", None)
    display_results(result)


def _run_graph(project_path, max_files, include_tests, verbose_mode):
    """Run the pipeline, streaming progress: one line per file as it finishes."""
    progress = st.progress(0, text="Scanning project…")
    log = st.container(border=True)
    try:
        graph = create_graph()
        initial_state = State(
            project_path=project_path,
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
            structured_analyses=[],
        )
        # Each file takes a few graph steps (node + checker), so the default limit of 25 is too low.
        config = {"recursion_limit": 500, "configurable": {
            "project_path": project_path,
            "max_files": max_files,
            "include_tests": include_tests,
            "verbose": verbose_mode,
        }}

        async def stream():
            state, total, shown, aggregating = {}, None, 0, False
            async for state in graph.astream(initial_state, config, stream_mode="values"):
                if total is None and state.get("analysis_complete"):
                    total = sum(len(state.get(k) or []) for k in (
                        "files_to_process_with_cobol", "files_to_process_with_vb6",
                        "files_to_process_with_fortran", "files_to_process_with_generic"))
                    langs = ", ".join(state.get("detected_languages") or []) or "none"
                    log.markdown(f"**{total} files** to analyse · languages: {langs}")
                done = state.get("functionality_analyses") or []
                for a in done[shown:]:
                    ok = a.get("processing_status") == "completed"
                    n = len(a.get("functionalities") or [])
                    log.write(f"{'🟢' if ok else '🔴'} {a.get('filename', '?')} "
                              f"({a.get('language', '?')}) · {n} functionalities")
                shown = len(done)
                if total:
                    frac = min(shown / total, 1.0)
                    if shown >= total and not aggregating:
                        aggregating = True
                        progress.progress(0.95, text="Grouping files into modules…")
                    elif not aggregating:
                        progress.progress(0.05 + 0.85 * frac, text=f"Analysing files… {shown}/{total}")
            return state

        result = asyncio.run(stream())
        progress.progress(1.0, text="✅ Done!")
        return result
    except Exception as e:
        progress.empty()
        st.error(f"❌ {e}")
        if verbose_mode:
            st.exception(e)
        return None


# ─── Results display ──────────────────────────────────────────────────────────

def display_results(results: Dict[str, Any]):
    st.success("✅ Analysis complete!")

    analyses = results.get("functionality_analyses", [])
    processed = results.get("processed_files", [])
    ok = sum(1 for a in analyses if a.get("processing_status") == "completed")
    modules = results.get("modules") or []

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Languages", len(results.get("detected_languages", [])))
    col2.metric("Frameworks", len(results.get("detected_frameworks", [])))
    col3.metric("Files analysed", f"{ok}/{len(analyses)}")
    col4.metric("Modules", len(modules))

    agg = results.get("aggregation_status", "")
    if agg.startswith("error"):
        st.warning(f"Module aggregation failed: {agg[len('error: '):]}")
    elif agg.startswith("skipped"):
        st.info("Module aggregation skipped: no file was analysed successfully.")

    errors = {Path(p.get("file_path", "")).name: p.get("message", "")
              for p in processed if p.get("processing_status") != "completed"}

    if analyses:
        st.markdown("### 🔍 Per-file analysis")
        for a in analyses:
            fname = a.get("filename") or Path(a.get("file_path", "unknown")).name
            lang = a.get("language", "?")
            status = a.get("processing_status", "unknown")
            icon = "🟢" if status == "completed" else "🔴" if status == "error" else "🟡"
            with st.expander(f"📄 {fname} ({lang}) {icon}"):
                st.write(f"**Node:** `{a.get('node_type', '?')}`")
                st.write(f"**Path:** `{a.get('file_path', '?')}`")
                if status != "completed" and errors.get(fname):
                    st.error(errors[fname])
                funcs = a.get("functionalities", [])
                if funcs:
                    for i, f in enumerate(funcs, 1):
                        st.write(f"{i}. {f}")
                elif status == "completed":
                    st.warning("No functionalities extracted")

    if modules:
        st.info("🧩 See the **Results** tab for the generated modules, and **Chat** to ask questions.")
    else:
        st.info("💬 Switch to the **Chat** tab to ask questions about this codebase.")


def display_modules(modules: List[Dict[str, Any]]):
    """Modules built by the aggregation node (RFP format)."""
    for m in modules:
        name = m.get("module_name", "module")
        with st.expander(f"🧩 {name}", expanded=False):
            st.write(m.get("module_description", ""))
            stack = m.get("tech_stack") or []
            if stack:
                st.markdown("**Tech stack:** " + " · ".join(f"`{t}`" for t in stack))
            if m.get("expected_output"):
                st.markdown(f"**Expected output:** {m['expected_output']}")
            endpoints = m.get("endpoints") or []
            if endpoints:
                st.markdown("**Endpoints**")
                st.table([{"Method": e.get("method", ""), "Path": e.get("path", "")}
                          for e in endpoints if isinstance(e, dict)])
            entities = m.get("entities") or {}
            if isinstance(entities, dict) and entities:
                st.markdown("**Entities**")
                cols = st.columns(min(3, len(entities)))
                for i, (ent, fields) in enumerate(entities.items()):
                    with cols[i % len(cols)]:
                        st.markdown(f"**{ent}**")
                        if isinstance(fields, dict):
                            st.code("\n".join(f"{k}: {v}" for k, v in fields.items()), language="yaml")
                        else:
                            st.write(fields)


def display_structure(structured: List[Dict[str, Any]]):
    """Structured per-file architecture from the generic analyser."""
    for s in structured:
        summary = s.get("file_summary") or {}
        fname = s.get("filename") or summary.get("file_name", "file")
        with st.expander(f"🏗️ {fname} — {summary.get('role', '')}"):
            if summary.get("purpose"):
                st.write(summary["purpose"])
            structure = s.get("structure") or {}
            classes = structure.get("classes") or []
            if classes:
                st.markdown("**Classes**")
                st.table([{
                    "Name": c.get("name", ""),
                    "Type": c.get("type", ""),
                    "Methods": len(c.get("methods") or []),
                    "Role": c.get("functionality", ""),
                } for c in classes])
            functions = structure.get("functions") or []
            if functions:
                st.markdown("**Functions**")
                st.table([{"Name": f.get("name", ""), "Role": f.get("functionality", f.get("purpose", ""))}
                          for f in functions if isinstance(f, dict)])
            patterns = structure.get("design_patterns") or []
            if patterns:
                st.markdown("**Design patterns:** " + ", ".join(
                    p if isinstance(p, str) else str(p.get("name", p)) for p in patterns))
            deps = structure.get("dependencies")
            if deps:
                with st.popover("Dependencies"):
                    st.json(deps)


# ─── Results tab ──────────────────────────────────────────────────────────────

def results_tab():
    if "analysis_results" not in st.session_state:
        st.info("Run an analysis first.")
        return

    results = st.session_state["analysis_results"]
    st.header("📊 Detailed results")
    st.caption(f"Project: {st.session_state.get('project_path', 'N/A')}")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("💾 Export JSON"):
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "⬇️ Download",
                data=json.dumps(results, indent=2, ensure_ascii=False),
                file_name=f"legacylens_{ts}.json",
                mime="application/json",
            )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Languages")
        for l in results.get("detected_languages", []):
            st.write(f"• {l}")
    with col2:
        st.subheader("Frameworks")
        for f in results.get("detected_frameworks", []):
            st.write(f"• {f}")

    modules = results.get("modules") or []
    st.subheader(f"🧩 Modules ({len(modules)})")
    if modules:
        st.caption("Files grouped into functional modules, ready for a modernisation RFP.")
        display_modules(modules)
        st.download_button("⬇️ Download modules JSON",
                           data=json.dumps(modules, indent=2, ensure_ascii=False),
                           file_name="legacylens_modules.json", mime="application/json")
    else:
        st.info(f"No modules generated ({results.get('aggregation_status') or 'aggregation did not run'}).")

    structured = results.get("structured_analyses") or []
    if structured:
        st.subheader(f"🏗️ File architecture ({len(structured)})")
        display_structure(structured)

    with st.expander("Raw JSON"):
        st.json(results)


# ─── Stats tab ────────────────────────────────────────────────────────────────

def statistics_tab():
    if "analysis_results" not in st.session_state:
        st.info("Run an analysis first.")
        return

    results = st.session_state["analysis_results"]
    st.header("📈 Statistics")

    processed = results.get("processed_files", [])
    node_counts = {"COBOL": 0, "VB6": 0, "Fortran": 0, "Generic": 0}
    node_map = {"cobol_node": "COBOL", "vb6_node": "VB6", "fortran_node": "Fortran", "generic_node": "Generic"}

    for f in processed:
        key = node_map.get(f.get("node_type", ""), "Generic")
        node_counts[key] += 1

    try:
        import pandas as pd
        df = pd.DataFrame(list(node_counts.items()), columns=["Node", "Files"])
        if df["Files"].sum() > 0:
            st.bar_chart(df.set_index("Node"))
            try:
                import plotly.express as px
                fig = px.pie(df[df["Files"] > 0], values="Files", names="Node",
                             title="File distribution by node")
                st.plotly_chart(fig, width="stretch")
            except ImportError:
                pass
    except ImportError:
        for node, count in node_counts.items():
            if count:
                st.write(f"• {node}: {count}")


# ─── Chat tab ─────────────────────────────────────────────────────────────────

def chat_tab():
    st.header("💬 Chat about this codebase")

    if "analysis_results" not in st.session_state:
        st.info("Run an analysis first, then come back here to ask questions.")
        return

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if user_prompt := st.chat_input("Ask about this codebase — e.g. 'How should we modernise the Fortran code?'"):
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                context = build_chat_context(st.session_state["analysis_results"])
                reply = chat_with_context(user_prompt, context, st.session_state.chat_history)
            st.markdown(reply)

        st.session_state.chat_history.append({"role": "assistant", "content": reply})

    if st.session_state.chat_history:
        if st.button("🗑️ Clear chat"):
            st.session_state.chat_history = []
            st.rerun()


if __name__ == "__main__":
    main()
