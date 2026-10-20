"""
LegacyLens: Streamlit UI
Multi-agent legacy system analyser with interactive chat.
"""

import sys
# ponytail: pipeline code prints emojis; Windows console is CP1252, so force UTF-8 once here
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import os
import streamlit as st
import sys
import asyncio
import html
import json
import re
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
    page_icon=":material/manage_search:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Colours and fonts live in .streamlit/config.toml; shadows and shapes in theme.css.
st.markdown(f"<style>{(current_dir / 'theme.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


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
        return f"**{hint}**\n\n`{type(e).__name__}: {str(e)[:200]}`"


# ─── Main UI ──────────────────────────────────────────────────────────────────

def main():
    st.markdown('<p class="ll-eyebrow">Legacy code analysis</p>', unsafe_allow_html=True)
    st.title("LegacyLens", anchor=False)
    st.caption("Reads every file of a COBOL, VB6, Fortran or modern codebase, groups them into "
               "business modules and draws the architecture.")

    with st.sidebar:
        # The Gemini key normally comes from .env; only ask for it when it's missing.
        if not os.getenv("GOOGLE_API_KEY"):
            st.subheader("Gemini API key", anchor=False)
            val = st.text_input("Gemini API key", type="password", label_visibility="collapsed",
                                placeholder="Paste your Gemini API key")
            if val:
                os.environ["GOOGLE_API_KEY"] = val
            st.markdown("---")

        st.subheader("GitHub", anchor=False)
        env_token = os.getenv("GITHUB_TOKEN")
        if st.checkbox("Private repository", value=bool(env_token),
                       help="Only needed for private repos. Public repos work without a token."):
            val = st.text_input("GitHub token", type="password", label_visibility="collapsed",
                                placeholder="Token loaded from .env" if env_token else "Paste a GitHub token")
            if val:
                os.environ["GITHUB_TOKEN"] = val

        st.markdown("---")
        st.subheader("Options", anchor=False)
        max_files = st.slider("Max files to analyse", 1, 100, 20)
        include_tests = st.checkbox("Include test files", value=False)
        verbose_mode = st.checkbox("Verbose mode", value=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Analyse", "Results", "Statistics", "Chat"])

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
    st.subheader("Choose a project", anchor=False)

    option = st.radio(
        "Input method:",
        ["Local path", "GitHub URL", "Upload ZIP"],
        horizontal=True,
    )

    project_path = None
    github_url = None
    branch = None

    if option == "Local path":
        project_path = st.text_input("Project path:", placeholder=r"C:\path\to\project")
        if project_path and os.path.exists(project_path):
            st.success(f"Found {project_path}", icon=":material/folder_open:")
        elif project_path:
            st.error("Path not found", icon=":material/close:")

    elif option == "GitHub URL":
        github_url = st.text_input("GitHub URL:", placeholder="https://github.com/owner/repo")
        if github_url:
            if not github_url.startswith("https://github.com/"):
                st.error("The URL must start with https://github.com/", icon=":material/close:")
            else:
                st.success(github_url, icon=":material/check:")
                branch = st.text_input("Branch (optional):", placeholder="main")

    elif option == "Upload ZIP":
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
            st.success(f"Extracted {uploaded.name}", icon=":material/check:")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Run analysis", type="primary", icon=":material/play_arrow:", width="stretch"):
            if not project_path and not github_url:
                st.error("Choose a project first", icon=":material/close:")
                return
            if not os.getenv("GOOGLE_API_KEY"):
                st.error("A Google API key is required", icon=":material/close:")
                return
            if github_url:
                run_github_analysis(github_url, branch, max_files, include_tests, verbose_mode)
            else:
                run_analysis(project_path, max_files, include_tests, verbose_mode)


def run_github_analysis(github_url, branch, max_files, include_tests, verbose_mode):
    st.subheader("Analysing repository", anchor=False)
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
        st.error(str(e), icon=":material/error:")
        if verbose_mode:
            st.exception(e)
    finally:
        try:
            analyzer.cleanup()
        except Exception:
            pass


def run_analysis(project_path, max_files, include_tests, verbose_mode):
    st.subheader("Analysing", anchor=False)
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
    log = st.container(key="run_log")
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
                    mark = ":green[:material/check_circle:]" if ok else ":red[:material/error: failed]"
                    log.write(f"{mark} **{a.get('filename', '?')}** · {a.get('language', '?')} · {n} functionalities")
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
        progress.progress(1.0, text="Done")
        return result
    except Exception as e:
        progress.empty()
        st.error(str(e), icon=":material/error:")
        if verbose_mode:
            st.exception(e)
        return None


# ─── Results display ──────────────────────────────────────────────────────────

def _clean(text: Any) -> str:
    """Text safe inside a Markdown badge."""
    return re.sub(r"[\[\]:]", "", " ".join(str(text).split()))


def _badges(items, color: str = "violet", limit: int = 0) -> str:
    items = [_clean(i) for i in items if str(i).strip()]
    shown = items[:limit] if limit else items
    extra = len(items) - len(shown)
    return " ".join(f":{color}-badge[{i}]" for i in shown) + (f" :gray-badge[+{extra}]" if extra else "")


def _short(text: Any, n: int = 140) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def _card_title(text: str):
    st.markdown(f'<p class="ll-card-title">{html.escape(str(text))}</p>', unsafe_allow_html=True)


def _grid(items: list, render, cols: int = 3):
    """Lay out cards in rows of `cols`."""
    for start in range(0, len(items), cols):
        for col, (i, item) in zip(st.columns(cols), enumerate(items[start:start + cols], start)):
            with col:
                render(item, i)


def _table(rows: List[Dict[str, Any]]):
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")


def overview(results: Dict[str, Any]):
    analyses = results.get("functionality_analyses", [])
    ok = sum(1 for a in analyses if a.get("processing_status") == "completed")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Languages", len(results.get("detected_languages", [])))
    col2.metric("Frameworks", len(results.get("detected_frameworks", [])))
    col3.metric("Files analysed", f"{ok}/{len(analyses)}")
    col4.metric("Modules", len(results.get("modules") or []))


def aggregation_notice(results: Dict[str, Any]):
    agg = results.get("aggregation_status") or ""
    if agg.startswith("error"):
        st.warning("The files couldn't be grouped into modules this time. Run the analysis again.",
                   icon=":material/warning:")
        st.caption(_short(agg[len("error: "):], 200))
    elif agg.startswith("skipped"):
        st.info("No module grouping: no file was analysed successfully.", icon=":material/info:")


def display_results(results: Dict[str, Any]):
    """Short summary under the live log; the full view is the Results tab."""
    st.success("Analysis complete. Open the **Results** tab for modules, diagrams and files, "
               "or **Chat** to ask questions.", icon=":material/check:")
    overview(results)
    aggregation_notice(results)


# Modules

def module_details(m: Dict[str, Any]):
    st.write(m.get("module_description", ""))
    if m.get("source_files"):
        st.markdown("**Files**  \n" + _badges(m["source_files"], "blue"))
    if m.get("tech_stack"):
        st.markdown("**Tech stack**  \n" + _badges(m["tech_stack"]))
    if m.get("expected_output"):
        st.markdown(f"**Expected output**  \n{m['expected_output']}")
    endpoints = [e for e in m.get("endpoints") or [] if isinstance(e, dict)]
    if endpoints:
        st.markdown("**Endpoints**")
        _table([{"Method": e.get("method", ""), "Path": e.get("path", ""),
                 "Description": e.get("description", "")} for e in endpoints])
    entities = {k: v for k, v in (m.get("entities") or {}).items() if isinstance(v, dict)}
    if entities:
        st.markdown("**Entities**")
        names = list(entities)
        for start in range(0, len(names), 2):
            for col, ent in zip(st.columns(2), names[start:start + 2]):
                with col:
                    st.markdown(f"**{ent}**")
                    _table([{"Field": k, "Type": str(v)} for k, v in entities[ent].items()])


def module_card(m: Dict[str, Any], i: int):
    name = m.get("module_name", "Module")
    with st.container(border=True, height=270, key=f"card_mod_{i}"):
        _card_title(name)
        st.caption(_short(m.get("module_description")))
        if m.get("tech_stack"):
            st.markdown(_badges(m["tech_stack"], limit=3))
        counts = [f"{len(m.get(k) or [])} {label}" for k, label in
                  (("source_files", "files"), ("endpoints", "endpoints"), ("entities", "entities"))]
        st.caption(" · ".join(counts))
        if st.button("Details", key=f"mod_details_{i}", icon=":material/open_in_full:"):
            st.dialog(name, width="large")(module_details)(m)


# Files

def file_details(a: Dict[str, Any], s: Dict[str, Any], error: str):
    summary = s.get("file_summary") or {}
    structure = s.get("structure") or {}
    arch = s.get("architecture") or {}
    st.caption(a.get("file_path", ""))
    if error:
        st.error(error, icon=":material/error:")

    tabs = {"Overview": True,
            "Classes": bool(structure.get("classes")),
            "Functions": bool(structure.get("functions")),
            "Dependencies": bool(structure.get("dependencies"))}
    names = [t for t, show in tabs.items() if show]
    for tab, name in zip(st.tabs(names), names):
        with tab:
            if name == "Overview":
                badges = [x for x in (a.get("language"), summary.get("role"), arch.get("layer")) if x]
                if badges:
                    st.markdown(_badges(badges))
                purpose = s.get("functional_description") or summary.get("purpose")
                if purpose:
                    st.write(purpose)
                if arch.get("responsibilities"):
                    st.markdown("**Responsibilities**")
                    st.markdown("\n".join(f"- {r}" for r in arch["responsibilities"]))
                funcs = a.get("functionalities") or []
                if funcs:
                    st.markdown("**Functionalities**")
                    st.markdown("\n".join(f"{n}. {f}" for n, f in enumerate(funcs, 1)))
                patterns = structure.get("design_patterns") or []
                if patterns:
                    st.markdown("**Design patterns**  \n" + _badges(
                        p if isinstance(p, str) else p.get("name", p) for p in patterns))
            elif name == "Classes":
                _table([{"Name": c.get("name", ""), "Type": c.get("type", ""),
                         "Methods": len(c.get("methods") or []), "Role": c.get("functionality", "")}
                        for c in structure["classes"] if isinstance(c, dict)])
            elif name == "Functions":
                _table([{"Name": f.get("name", ""), "Role": f.get("functionality", f.get("purpose", ""))}
                        for f in structure["functions"] if isinstance(f, dict)])
            else:
                _table([{"Name": d.get("name", ""), "Type": d.get("type", ""), "Usage": d.get("usage", "")}
                        if isinstance(d, dict) else {"Name": str(d), "Type": "", "Usage": ""}
                        for d in structure["dependencies"]])


def file_cards(results: Dict[str, Any]):
    structured = {s.get("file_path"): s for s in results.get("structured_analyses") or []}
    errors = {p.get("file_path"): p.get("message", "") for p in results.get("processed_files", [])
              if p.get("processing_status") != "completed"}

    def card(a: Dict[str, Any], i: int):
        s = structured.get(a.get("file_path")) or {}
        summary = s.get("file_summary") or {}
        structure = s.get("structure") or {}
        fname = a.get("filename") or Path(a.get("file_path", "file")).name
        ok = a.get("processing_status") == "completed"
        with st.container(border=True, height=250, key=f"card_file_{i}"):
            _card_title(fname)
            badges = [_badges([a.get("language", "?")])]
            if summary.get("role"):
                badges.append(_badges([summary["role"]], "blue"))
            if not ok:
                badges.append(":red-badge[failed]")
            st.markdown(" ".join(badges))
            funcs = a.get("functionalities") or []
            st.caption(_short(summary.get("purpose") or "; ".join(map(str, funcs))
                              or errors.get(a.get("file_path")) or "No details"))
            if structure:
                st.caption(f"{len(structure.get('classes') or [])} classes · "
                           f"{len(structure.get('functions') or [])} functions")
            else:
                st.caption(f"{len(funcs)} functionalities")
            if st.button("Details", key=f"file_details_{i}", icon=":material/open_in_full:"):
                st.dialog(fname, width="large")(file_details)(a, s, errors.get(a.get("file_path"), ""))

    _grid(results.get("functionality_analyses", []), card)


DIAGRAM_TITLES = {"architecture": "Architecture", "entities": "Data model", "classes": "Classes"}
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"


def mermaid_html(code: str) -> str:
    """Standalone page that renders one Mermaid diagram (Streamlit has no native renderer)."""
    return f"""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap">
<style>
  body {{ margin: 0; padding: 12px; }}
  /* centred when it fits; when wider, starts at the left edge and scrolls (never cut off) */
  .mermaid svg {{ display: block; margin: 0 auto; }}
  /* clay: no sharp corners, even inside diagrams */
  .node rect, .er.entityBox, g.classGroup rect, rect.basic {{ rx: 14px; ry: 14px; }}
  .cluster rect {{ rx: 24px; ry: 24px; }}
</style>
<pre class="mermaid" style="background:transparent">{html.escape(code)}</pre>
<script type="module">
  import mermaid from "{MERMAID_JS}";
  // Same clay palette as .streamlit/config.toml and theme.css
  mermaid.initialize({{ startOnLoad: false, theme: "base", securityLevel: "strict",
                       themeVariables: {{ fontFamily: "Inter, sans-serif", fontSize: "14px",
                         background: "#FFFFFF", primaryColor: "#FFFFFF", primaryTextColor: "#332F3A",
                         primaryBorderColor: "#C4B5FD", lineColor: "#8B85A0", secondaryColor: "#F4F1FA",
                         tertiaryColor: "#FAF8FD", clusterBkg: "#F6F2FE", clusterBorder: "#DDD6FE",
                         titleColor: "#6D28D9", edgeLabelBackground: "#FFFFFF", textColor: "#332F3A",
                         attributeBackgroundColorOdd: "#FFFFFF", attributeBackgroundColorEven: "#F7F4FC" }},
                       flowchart: {{ useMaxWidth: false }}, class: {{ useMaxWidth: false }}, er: {{ useMaxWidth: false }} }});
  // Inactive Streamlit tabs are hidden, and Mermaid fails to draw in a hidden frame.
  // ponytail: poll until this frame has a size, then draw once.
  const timer = setInterval(() => {{
    if (!window.innerWidth || !document.body.clientWidth) return;
    clearInterval(timer);
    // Measure labels with Inter, not the fallback font, or text gets clipped in its box.
    Promise.all([document.fonts.load("14px Inter"), document.fonts.load("600 14px Inter")])
      .catch(() => {{}}).finally(() => mermaid.run());
  }}, 300);
</script>"""


def display_diagrams(diagrams: Dict[str, str]):
    """Mermaid diagrams built by the diagram node, one tab each."""
    import streamlit.components.v1 as components
    names = list(diagrams)
    for tab, name in zip(st.tabs([DIAGRAM_TITLES.get(n, n) for n in names]), names):
        with tab:
            components.html(mermaid_html(diagrams[name]), height=520, scrolling=True)
            with st.expander("Mermaid code"):
                st.code(diagrams[name], language="text")
            st.download_button(f"{name}.mmd", icon=":material/download:", data=diagrams[name],
                               file_name=f"legacylens_{name}.mmd", mime="text/plain", key=f"dl_{name}")


# ─── Results tab ──────────────────────────────────────────────────────────────

def results_tab():
    if "analysis_results" not in st.session_state:
        st.info("Run an analysis first.")
        return

    results = st.session_state["analysis_results"]
    head, export = st.columns([4, 1], vertical_alignment="bottom")
    with head:
        st.subheader("Results", anchor=False)
        st.caption(f"Project: {st.session_state.get('project_path', 'N/A')}")
    with export:
        st.download_button(
            "Export JSON", icon=":material/download:", width="stretch",
            data=json.dumps(results, indent=2, ensure_ascii=False),
            file_name="legacylens_results.json", mime="application/json",
        )

    overview(results)

    with st.container(border=True, key="card_stack"):
        col1, col2 = st.columns(2)
        with col1:
            _card_title("Languages")
            st.markdown(_badges(results.get("detected_languages", [])) or "None detected")
        with col2:
            _card_title("Frameworks")
            st.markdown(_badges(results.get("detected_frameworks", []), "blue") or "None detected")

    modules = results.get("modules") or []
    st.subheader(f"Modules ({len(modules)})", anchor=False)
    if modules:
        st.caption("Files grouped into functional modules, ready for a modernisation RFP.")
        _grid(modules, module_card)
    else:
        aggregation_notice(results)

    diagrams = results.get("diagrams") or {}
    if diagrams:
        st.subheader("Diagrams", anchor=False)
        display_diagrams(diagrams)

    analyses = results.get("functionality_analyses", [])
    if analyses:
        st.subheader(f"Files ({len(analyses)})", anchor=False)
        file_cards(results)


# ─── Stats tab ────────────────────────────────────────────────────────────────

def statistics_tab():
    if "analysis_results" not in st.session_state:
        st.info("Run an analysis first.")
        return

    results = st.session_state["analysis_results"]
    st.subheader("Statistics", anchor=False)

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
    st.subheader("Ask about this codebase", anchor=False)

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
    if user_prompt := st.chat_input("Ask about this codebase, for example: how should we modernise the Fortran code?"):
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
        if st.button("Clear chat", icon=":material/delete:"):
            st.session_state.chat_history = []
            st.rerun()


if __name__ == "__main__":
    main()
