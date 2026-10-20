# src/agent/nodes/fortran_node/extractor/functionality_extractor.py

from typing import Dict, List
from ..config import FUNCTIONALITY_DESCRIPTION_CONFIG
from ..utils import call_openrouter


def guess_purpose_from_name(name: str) -> str:
    """Try to infer what a function/subroutine does based on its name."""
    name = name.lower()
    if "read" in name:
        return "Reads input data"
    elif "write" in name:
        return "Writes output data"
    elif "init" in name:
        return "Initializes a process or variable"
    elif "compute" in name or "calc" in name:
        return "Performs a calculation"
    elif "print" in name:
        return "Displays or logs information"
    elif "update" in name:
        return "Updates internal state"
    elif "process" in name:
        return "Processes data"
    elif "load" in name:
        return "Loads data from a file or database"
    elif "save" in name:
        return "Saves results to a file"
    return "Performs a specific operation"


from typing import Dict, List

def extract_modules(parsed: Dict) -> List[Dict]:
    functionalities = []
    for mod in parsed.get("modules", []):
        functionalities.append({
            "type": "module",
            "name": mod,
            "description": f"Defines a module named '{mod}' which likely encapsulates related procedures and data."
        })
    return functionalities


def extract_derived_types(parsed: Dict) -> List[Dict]:
    functionalities = []
    for derived in parsed.get("types", []):
        name = derived.get("name", "")
        inherits = derived.get("inherits")
        attributes = derived.get("attributes", [])
        methods = derived.get("methods", [])

        attr_desc = ", ".join([f"{a['name']} ({a['type']})" for a in attributes]) or "none"
        inherit_desc = f"inherits from '{inherits}'" if inherits else "no inheritance"

        prompt = f"""You are a code summarizer. Describe what the following Fortran derived type (class) represents and its purpose in one concise sentence.

    Derived type '{name}':
    Attributes: {attr_desc}
    Inheritance: {inherit_desc}
    Methods: {', '.join([m['name'] for m in methods]) if methods else 'none'}

    Description:"""

        summary = call_openrouter(prompt, FUNCTIONALITY_DESCRIPTION_CONFIG) or \
                f"Defines a class-like derived type '{name}' {inherit_desc} with attributes: {attr_desc}."

        functionalities.append({
            "type": "class",
            "name": name,
            "inherits": inherits,
            "attributes": attributes,
            "methods": [m['name'] for m in methods],
            "description": summary
        })
    return functionalities


def extract_subroutines(parsed: Dict) -> List[Dict]:
    functionalities = []
    for sub in parsed.get("subroutines", []):
        name = sub.get("name", "")
        body = sub.get("body", "")
        parameters = sub.get("parameters", [])

        param_strs = [f"{p['name']} ({p['type']}, intent={p['intent']})" for p in parameters]
        param_desc = ", ".join(param_strs)

        prompt = f"""You are a code summarizer. Describe what the following Fortran subroutine does in one concise sentence.

        Fortran subroutine:
        {body}

        Summary:"""

        summary = call_openrouter(prompt, FUNCTIONALITY_DESCRIPTION_CONFIG) or guess_purpose_from_name(name)

        functionalities.append({
            "type": "subroutine",
            "name": name,
            "description": f"Subroutine '{name}': {summary}",
            "parameters": parameters
        })
    return functionalities


def extract_functions(parsed: Dict) -> List[Dict]:
    functionalities = []
    for func in parsed.get("functions", []):
        name = func.get("name", "")
        body = func.get("body", "")
        parameters = func.get("parameters", [])
        return_type = func.get("return_type")
        return_var = func.get("return_var")

        param_strs = [f"{p['name']} ({p['type']}, intent={p['intent']})" for p in parameters]
        param_desc = ", ".join(param_strs)
        return_desc = f"{return_type}" if return_type else "unknown"

        prompt = f"""You are a code summarizer. Describe what the following Fortran function does in one concise sentence.

        Fortran function:
        {body}

        Summary:"""

        summary = call_openrouter(prompt, FUNCTIONALITY_DESCRIPTION_CONFIG) or guess_purpose_from_name(name)

        functionalities.append({
            "type": "function",
            "name": name,
            "description": f"Function '{name}': {summary}",
            "parameters": parameters,
            "return": {
                "name": return_var,
                "type": return_type
            }
        })
    return functionalities


def extract_functionalities(parsed: Dict) -> Dict:
    functionalities = []
    functionalities.extend(extract_modules(parsed))
    functionalities.extend(extract_derived_types(parsed))
    functionalities.extend(extract_subroutines(parsed))
    functionalities.extend(extract_functions(parsed))

    # Remove duplicates by (type, name)
    unique_set = set()
    deduped_functionalities = []

    for item in functionalities:
        key = (item["type"], item["name"])
        if key not in unique_set:
            unique_set.add(key)
            deduped_functionalities.append(item)

    return {
        "functionalities": deduped_functionalities,
        "fortran_version": parsed.get("fortran_version"),
        "file_path": parsed.get("file_path")
    }

