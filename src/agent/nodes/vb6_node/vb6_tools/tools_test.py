# --- Import des fonctions à tester ---
from pathlib import Path

# Tu peux adapter ici les noms selon ton organisation de fichier
from agent.nodes.vb6_node.vb6_tools import (  # Remplace 'your_module' par le nom réel de ton fichier sans `.py`
    _determine_file_type,
    _extract_procedures,
    _extract_variables,
    _extract_controls,
    _extract_events,
    _extract_api_declarations,
    _calculate_complexity_score,
)

def test_vb6_analysis(file_path: str):
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        print(f"Fichier introuvable : {file_path}")
        return

    code = path.read_text(encoding="utf-8", errors="ignore")

    print(f"\nAnalyse du fichier : {file_path}")
    print("Type de fichier :", _determine_file_type(code))
    
    procedures = _extract_procedures(code)
    print("\nProcédures trouvées :")
    for p in procedures:
        print(p)
    
    variables = _extract_variables(code)
    print("\nVariables trouvées :")
    for v in variables:
        print(v)
    
    controls = _extract_controls(code)
    print("\nContrôles trouvés :")
    for c in controls:
        print(c)
    
    events = _extract_events(code)
    print("\nÉvénements trouvés :")
    for e in events:
        print(e)
    
    api_decls = _extract_api_declarations(code)
    print("\nDéclarations API trouvées :")
    for a in api_decls:
        print(a)
    
    complexity = _calculate_complexity_score(procedures, variables, controls)
    print("\nScore de complexité :", complexity)

# --- Lancer le test ---
if __name__ == "__main__":
    test_vb6_analysis("C:\\Users\\Administrator\\Documents\\Stage\\Talan\\VB6\\MDI Application\\MDI Application.vbp")