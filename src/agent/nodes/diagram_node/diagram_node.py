"""Diagram node: turns the analysis into Mermaid diagrams.

Runs after the aggregation node. Built straight from the state (no LLM call),
so it costs no quota and the Mermaid syntax is always valid.

Diagrams:
- architecture: modules as boxes holding their files, arrows for imports
- entities:     ER diagram of the module entities, links from `<entity>_id` fields
- classes:      class diagram of the classes found by the structured analyser
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

OUTPUT_DIR = Path(__file__).resolve().parents[4] / "outputs" / "diagrams"

LEGACY_LANGUAGES = {"cobol", "vb6", "fortran"}
MAX_MEMBERS = 8   # per class, keeps the class diagram readable
MAX_CLASSES = 20


def _id(text: str, prefix: str = "n") -> str:
    """Mermaid node id: letters, digits and underscores only."""
    return prefix + "_" + (re.sub(r"\W+", "_", str(text)).strip("_") or "x")


def _label(text: Any) -> str:
    """Text safe inside a quoted Mermaid label."""
    return re.sub(r'["`<>{}\[\]|]', "", str(text)).strip() or "?"


def _word(text: Any, default: str = "x") -> str:
    """One bare word (ER types and names, class member names)."""
    return re.sub(r"\W+", "_", str(text)).strip("_") or default


def _member(text: Any) -> str:
    """Class member name, keeping leading underscores (_private, __init__)."""
    return re.sub(r"\W+", "_", str(text)) or "x"


def _dep_names(structure: Dict[str, Any]) -> List[str]:
    deps = structure.get("dependencies") or []
    names = [d.get("name", "") if isinstance(d, dict) else str(d) for d in deps]
    return [n for n in names if n]


def architecture_diagram(modules: List[Dict[str, Any]], analyses: List[Dict[str, Any]],
                         structured: List[Dict[str, Any]]) -> str:
    files = [a for a in analyses if a.get("filename")]
    if not files:
        return ""

    lines = ["flowchart LR"]
    placed = set()
    for m in modules:
        members = [f for f in m.get("source_files") or [] if any(a["filename"] == f for a in files)]
        if not members:
            continue
        lines.append(f'  subgraph {_id(m.get("module_name", "module"), "m")}["{_label(m.get("module_name", "module"))}"]')
        for f in members:
            if f not in placed:
                lines.append(f'    {_id(f, "f")}["{_label(f)}"]')
                placed.add(f)
        lines.append("  end")

    rest = [a["filename"] for a in files if a["filename"] not in placed]
    if rest:
        title = "Other files" if placed else "Files"
        lines.append(f'  subgraph m_other["{title}"]')
        for f in rest:
            lines.append(f'    {_id(f, "f")}["{_label(f)}"]')
        lines.append("  end")

    # Imports between project files: a dependency named like another file's stem.
    stems = {Path(a["filename"]).stem.lower(): a["filename"] for a in files}
    edges = set()
    for s in structured:
        src = s.get("filename")
        for dep in _dep_names(s.get("structure") or {}):
            target = stems.get(dep.split(".")[-1].lower()) or stems.get(dep.split(".")[0].lower())
            if target and target != src:
                edges.add((src, target))
    if not placed and not edges:
        return ""  # no modules, no imports: just a row of file names, nothing to draw
    for src, target in sorted(edges):
        lines.append(f"  {_id(src, 'f')} --> {_id(target, 'f')}")

    legacy = [a["filename"] for a in files if a.get("language") in LEGACY_LANGUAGES]
    if legacy:
        lines.append("  classDef legacy fill:#FCE7F3,stroke:#DB2777,color:#332F3A")
        lines.append(f"  class {','.join(_id(f, 'f') for f in legacy)} legacy")
    return "\n".join(lines)


def entity_diagram(modules: List[Dict[str, Any]]) -> str:
    entities: Dict[str, Dict[str, Any]] = {}
    for m in modules:
        for name, fields in (m.get("entities") or {}).items():
            if isinstance(fields, dict):
                entities.setdefault(_word(name, "Entity"), {}).update(fields)
    if not entities:
        return ""

    lines = ["erDiagram"]
    for name, fields in entities.items():
        lines.append(f"  {name} {{")
        for field, ftype in fields.items():
            lines.append(f"    {_word(ftype, 'string')} {_word(field)}")
        lines.append("  }")

    # customer_id in Order -> Customer has many Order
    by_lower = {n.lower(): n for n in entities}
    links = set()
    for name, fields in entities.items():
        for field in fields:
            if field.lower().endswith("_id"):
                target = by_lower.get(field[:-3].lower().replace("_", ""))
                if target and target != name:
                    links.add((target, name, field))
    for target, name, field in sorted(links):
        lines.append(f'  {target} ||--o{{ {name} : "{_label(field)}"')
    return "\n".join(lines)


def class_diagram(structured: List[Dict[str, Any]]) -> str:
    classes = {}
    for s in structured:
        for c in (s.get("structure") or {}).get("classes") or []:
            name = _word(c.get("name"), "")
            if name and name not in classes:
                classes[name] = c
    # ponytail: enums and plain data classes swamp the picture (one 18000px row on a
    # 60-class project); keep the classes with behaviour, capped. Data classes are in the ER diagram.
    with_methods = {n: c for n, c in classes.items() if c.get("methods")}
    classes = dict(list((with_methods or classes).items())[:MAX_CLASSES])

    lines, links = ["classDiagram"], set()
    for name, c in classes.items():
        body = []
        ctype = str(c.get("type") or "").lower()
        if ctype in ("interface", "enum", "abstract"):
            body.append(f"    <<{ctype}>>")
        for a in (c.get("attributes") or [])[:MAX_MEMBERS]:
            if isinstance(a, dict) and a.get("name"):
                sign = "-" if a.get("visibility") == "private" else "+"
                atype = _word(a.get("type") or "Any")
                body.append(f"    {sign}{_member(a['name'])} {atype}")
                # an attribute typed as another drawn class (also Optional_X, List_X) is a link
                for part in atype.split("_"):
                    if part in classes and part != name:
                        links.add((name, part))
        for meth in (c.get("methods") or [])[:MAX_MEMBERS]:
            mname = meth.get("name") if isinstance(meth, dict) else meth
            if mname:
                sign = "-" if isinstance(meth, dict) and meth.get("visibility") == "private" else "+"
                body.append(f"    {sign}{_member(mname)}()")
        lines += [f"  class {name} {{", *body, "  }"] if body else [f"  class {name}"]
    lines += [f"  {a} --> {b}" for a, b in sorted(links)]
    return "\n".join(lines) if classes else ""


def build_diagrams(modules, analyses, structured) -> Dict[str, str]:
    diagrams = {
        "architecture": architecture_diagram(modules, analyses, structured),
        "entities": entity_diagram(modules),
        "classes": class_diagram(structured),
    }
    return {k: v for k, v in diagrams.items() if v}


async def diagram_node(state, config: RunnableConfig) -> Dict[str, Any]:
    """Build Mermaid diagrams and save them as .mmd files."""
    print("DIAGRAM_NODE: building Mermaid diagrams")
    analyses = [a for a in state.functionality_analyses if a.get("processing_status") == "completed"]
    diagrams = build_diagrams(state.modules, analyses, state.structured_analyses)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for name, code in diagrams.items():
            (OUTPUT_DIR / f"{name}.mmd").write_text(code, encoding="utf-8")
    except OSError as e:
        print(f"  could not save diagrams: {e}")
    print(f"  built: {', '.join(diagrams) or 'none'}")
    return {"diagrams": diagrams}
