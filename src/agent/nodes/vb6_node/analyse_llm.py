import requests
import json
import os
from ds_llm import analyze_vb6_file
from dotenv import load_dotenv

load_dotenv()

def analyze_existing_file(file_path):
    """
    Analyser un fichier VB6 existant
    
    Args:
        file_path (str): Chemin vers le fichier VB6 existant
    """
    if not os.path.exists(file_path):
        print(f"❌ Fichier {file_path} non trouvé")
        return
    
    print(f"🔍 Analyse de: {file_path}")
    result = analyze_vb6_file(file_path)
    
    if result:
        print("\n✅ Analyse réussie!")
        print("📊 Résultat JSON:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Sauvegarder le résultat dans vb6_analysis.json
        with open('vb6_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("💾 Résultat sauvegardé dans: vb6_analysis.json")
        return result
    else:
        print("\n❌ Échec de l'analyse")
        return None

if __name__ == "__main__":
    # Vérifier la clé API
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ Variable d'environnement OPENROUTER_API_KEY non définie")
        print("💡 Définissez votre clé: export OPENROUTER_API_KEY='votre_cle'")
        exit(1)
    
    print("🚀 Testeur d'analyseur VB6 avec DeepSeek")
    print("=" * 50)

    analyze_existing_file("C:\\Users\\Administrator\\Documents\\Stage\\Talan\\VB6\\Calculator\\frmCalculator.frm")