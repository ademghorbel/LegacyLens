"""
LegacyLens — Streamlit UI
Multi-agent legacy system analyser with interactive chat.
"""

import streamlit as st
import os
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
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)

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
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        return f"Error calling LLM: {e}"


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
        if st.button("🚀 Run analysis", type="primary", use_container_width=True):
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
    progress = st.progress(0)
    status = st.empty()
    try:
        status.text("Cloning repo…")
        progress.progress(10)
        analyzer = GitHubAnalyzer(os.getenv("GITHUB_TOKEN"))
        progress.progress(20)
        result = asyncio.run(analyzer.analyze_github_repository(
            github_url=github_url, branch=branch,
            max_files=max_files, include_tests=include_tests, verbose_mode=verbose_mode,
        ))
        progress.progress(90)
        st.session_state["analysis_results"] = result
        st.session_state["project_path"] = f"GitHub: {github_url}"
        st.session_state["github_metadata"] = result.get("github_metadata", {})
        st.session_state.pop("chat_history", None)  # reset chat for new analysis
        progress.progress(100)
        status.text("✅ Done!")
        try:
            analyzer.cleanup()
        except Exception:
            pass
        display_results(result)
    except Exception as e:
        st.error(f"❌ {e}")
        if verbose_mode:
            st.exception(e)


def run_analysis(project_path, max_files, include_tests, verbose_mode):
    st.header("🔄 Analysing…")
    progress = st.progress(0)
    status = st.empty()
    try:
        status.text("Initialising graph…")
        progress.progress(10)
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
        )
        config = {"configurable": {
            "project_path": project_path,
            "max_files": max_files,
            "include_tests": include_tests,
            "verbose": verbose_mode,
        }}
        progress.progress(20)
        status.text("Running agents…")
        result = asyncio.run(graph.ainvoke(initial_state, config))
        st.session_state["analysis_results"] = result
        st.session_state["project_path"] = project_path
        st.session_state.pop("chat_history", None)
        progress.progress(100)
        status.text("✅ Done!")
        display_results(result)
    except Exception as e:
        st.error(f"❌ {e}")
        if verbose_mode:
            st.exception(e)


# ─── Results display ──────────────────────────────────────────────────────────

def display_results(results: Dict[str, Any]):
    st.success("✅ Analysis complete!")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Languages", len(results.get("detected_languages", [])))
    col2.metric("Frameworks", len(results.get("detected_frameworks", [])))
    col3.metric("Files processed", len(results.get("processed_files", [])))
    col4.metric("Functionalities", len(results.get("functionality_analyses", [])))

    analyses = results.get("functionality_analyses", [])
    if analyses:
        st.markdown("### 🔍 Functionality analyses")
        for a in analyses:
            fname = a.get("filename") or Path(a.get("file_path", "unknown")).name
            lang = a.get("language", "?")
            status = a.get("processing_status", "unknown")
            icon = "🟢" if status == "completed" else "🔴" if status == "error" else "🟡"
            with st.expander(f"📄 {fname} ({lang}) {icon}"):
                st.write(f"**Node:** `{a.get('node_type', '?')}`")
                st.write(f"**Path:** `{a.get('file_path', '?')}`")
                funcs = a.get("functionalities", [])
                if funcs:
                    for i, f in enumerate(funcs, 1):
                        st.write(f"{i}. {f}")
                else:
                    st.warning("No functionalities extracted")

    st.info("💬 Switch to the **Chat** tab to ask questions about this codebase.")


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
                st.plotly_chart(fig, use_container_width=True)
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
