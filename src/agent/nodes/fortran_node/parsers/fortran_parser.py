# src/agent/nodes/fortran_node/parsers/fortran_parser.py

import re
from pathlib import Path
from typing import List, Dict


def read_fortran_file(file_path: str) -> str:
    return Path(file_path).read_text(encoding="utf-8")


def extract_modules(code: str) -> List[str]:
    return re.findall(r"\bmodule\s+(\w+)", code, re.IGNORECASE)


def extract_subroutines(code: str) -> List[Dict[str, str]]:
    pattern = re.compile(
        r"\bsubroutine\s+(\w+)\s*\(([^)]*)\)(.*?)end\s+subroutine\b(?:\s+\1)?",
        re.IGNORECASE | re.DOTALL
    )
    subroutines = []

    for match in pattern.finditer(code):
        name = match.group(1)
        param_list = [p.strip() for p in match.group(2).split(",") if p.strip()]
        body = match.group(3)

        param_info = []
        for line in body.splitlines():
            line = line.strip()
            for p in param_list:
                if re.search(rf"\b{re.escape(p)}\b", line):
                    decl = re.match(r"(\w+(?:\(.*?\))?),\s*intent\((\w+)\)\s*::\s*" + re.escape(p), line, re.IGNORECASE)
                    if decl:
                        param_info.append({
                            "name": p,
                            "type": decl.group(1),
                            "intent": decl.group(2)
                        })

        subroutines.append({
            "type": "subroutine",
            "name": name,
            "parameters": param_info,
            "body": match.group(0)
        })

    return subroutines


def extract_functions(code: str) -> List[Dict[str, str]]:
    function_blocks = []
    pattern = re.compile(
        r"\bfunction\s+(\w+)\s*\(([^)]*)\)\s*result\s*\(\s*(\w+)\s*\)(.*?)end\s+function\b(?:\s+\1)?",
        re.IGNORECASE | re.DOTALL
    )

    for match in pattern.finditer(code):
        name = match.group(1)
        params = [p.strip() for p in match.group(2).split(",") if p.strip()]
        return_var = match.group(3)
        body = match.group(4)

        # Parse parameter declarations
        param_info = []
        return_type = None
        for line in body.splitlines():
            line = line.strip()
            for p in params:
                if p in line:
                    decl = re.match(r"(\w+(?:\(.*?\))?),\s*intent\((\w+)\)\s*::\s*(\w+)", line, re.IGNORECASE)
                    if decl and decl.group(3) == p:
                        param_info.append({
                            "name": p,
                            "type": decl.group(1),
                            "intent": decl.group(2)
                        })

            if return_var in line:
                type_decl = re.match(r"(\w+(?:\(.*?\))?)\s*::\s*" + re.escape(return_var), line)
                if type_decl:
                    return_type = type_decl.group(1)

        function_blocks.append({
            "type": "function",
            "name": name,
            "parameters": param_info,
            "return_var": return_var,
            "return_type": return_type,
            "body": match.group(0)
        })

    return function_blocks


def extract_types(code: str) -> List[Dict]:
    type_pattern = re.compile(
        r"type(?:\s*,\s*extends\((\w+)\))?\s*::\s*(\w+)(.*?)end\s+type\b(?:\s+\2)?",
        re.IGNORECASE | re.DOTALL
    )
    
    attr_pattern = re.compile(r"(?:(\w+(?:\s*\(.*?\))?)\s*::\s*(.*))", re.IGNORECASE)

    types = []
    for match in type_pattern.finditer(code):
        parent = match.group(1)
        type_name = match.group(2)
        body = match.group(3)

        attributes = []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("procedure"):  # skip methods
                continue
            attr_match = attr_pattern.match(line)
            if attr_match:
                var_type = attr_match.group(1).strip()
                var_names = [v.strip() for v in attr_match.group(2).split(",")]
                for name in var_names:
                    attributes.append({"name": name, "type": var_type})

        types.append({
            "name": type_name,
            "inherits": parent,
            "attributes": attributes
        })

    return types


def extract_comments(code: str) -> List[str]:
    return [line.strip() for line in code.splitlines() if line.strip().startswith("!")]


def detect_fortran_versions(code: str) -> List[str]:
    """
    Attempts to infer possible Fortran versions based on language features used.
    Returns a list containing any of: 'Fortran 77', 'Fortran 90', 'Fortran 95', 'Fortran 2003',
    'Fortran 2008', 'Fortran 2018', or 'Unknown'.
    """

    versions = set()

    # Fortran 77 indicators
    if re.search(r"\bdimension\b|\bcommon\b|\bequivalence\b|\bgoto\b", code, re.IGNORECASE):
        versions.add("Fortran 77")

    # Fortran 90 indicators
    if re.search(r"\bmodule\b", code, re.IGNORECASE) or re.search(r"\bcontains\b", code, re.IGNORECASE):
        versions.add("Fortran 90")

    # Fortran 95 indicators
    if re.search(r"\bforall\b|\binterface\b", code, re.IGNORECASE):
        versions.add("Fortran 95")

    # Fortran 2003 indicators
    if re.search(r"\babstract interface\b|\bprocedure\b|\bextends\b|\bclass\b", code, re.IGNORECASE):
        versions.add("Fortran 2003")

    # Fortran 2008 indicators
    if re.search(r"\bsync all\b|\bsubmodule\b|\bcritical\b", code, re.IGNORECASE):
        versions.add("Fortran 2008")

    # Fortran 2018 indicators
    if re.search(r"\bblock\b|\bimport\b", code, re.IGNORECASE) and "submodule" in code:
        versions.add("Fortran 2018")

    if not versions:
        return ["Unknown"]

    return sorted(versions)


def parse_fortran_file(file_path: str) -> Dict:
    code = read_fortran_file(file_path)

    return {
        "file_path": file_path,
        "modules": extract_modules(code),
        "subroutines": extract_subroutines(code),
        "functions": extract_functions(code),
        "types": extract_types(code),
        "comments": extract_comments(code),
        "fortran_version": detect_fortran_versions(code),
        "raw_code": code
    }
