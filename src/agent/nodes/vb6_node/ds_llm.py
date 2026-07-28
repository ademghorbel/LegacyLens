import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

from vb6_prompts import generate_prompt

def analyze_vb6_file(file_path):
    """
    Analyse un fichier VB6 avec DeepSeek via OpenRouter
    
    Args:
        file_path (str): Chemin vers le fichier VB6
    
    Returns:
        dict: Résultat de l'analyse JSON
    """
    prompt = generate_prompt(file_path)

    try:
        # Lire le fichier VB6
        with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
            vb6_code = f.read()
        
        # Construire le message complet
        full_prompt = f"{prompt}\n\nCode VB6 à analyser :\n```vb6\n{vb6_code}\n```"
        
        # Headers pour OpenRouter
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        # Payload pour l'API
        payload = {
            "model": "deepseek/deepseek-chat-v3-0324",
            "messages": [
                {"role": "user", "content": full_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 10000
        }
        
        # Appel à l'API OpenRouter
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        # Vérifier le statut
        response.raise_for_status()
        
        # Extraire la réponse
        result_data = response.json()
        result_text = result_data["choices"][0]["message"]["content"].strip()
        
        # Nettoyer et parser le JSON
        if result_text.startswith('```json'):
            result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Parser le JSON
        analysis_result = json.loads(result_text)
        
        return analysis_result
        
    except FileNotFoundError:
        print(f"Erreur: Fichier {file_path} non trouvé")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erreur API: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Erreur JSON: {e}")
        print(f"Réponse brute: {result_text}")
        return None
    except Exception as e:
        print(f"Erreur: {e}")
        return None
    

def read_vb6_file(file_path):
    """
    Lit le contenu d'un fichier VB6

    Args:
        file_path (str): Chemin vers le fichier VB6

    Returns:
        str: Contenu du fichier VB6
    """
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        return f.read()

def build_full_prompt(prompt, vb6_code):
    """
    Construit le prompt complet avec le code VB6

    Args:
        prompt (str): Le prompt de base
        vb6_code (str): Le code VB6

    Returns:
        str: Prompt complet
    """
    return f"{prompt}\n\nCode VB6 à analyser :\n```vb6\n{vb6_code}\n```"

def call_deepseek_api(full_prompt):
    """
    Appelle l'API OpenRouter avec le prompt complet

    Args:
        full_prompt (str): Le prompt complet

    Returns:
        dict: Résultat de l'analyse JSON
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324",
        "messages": [
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1000
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        # Vérifier le statut
        response.raise_for_status()
        
        # Extraire la réponse
        result_data = response.json()
        result_text = result_data["choices"][0]["message"]["content"].strip()
        
        # Nettoyer et parser le JSON
        if result_text.startswith('```json'):
            result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Parser le JSON
        analysis_result = json.loads(result_text)
        
        return analysis_result

    except requests.exceptions.Timeout:
        print("Erreur: La requête a expiré.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erreur API: {e}")
        print(f"Payload envoyé: {payload}")
        return None
    except json.JSONDecodeError as e:
        print(f"Erreur JSON: {e}")
        print(f"Réponse brute: {response.text if response else 'Aucune réponse'}")
        return None
    except Exception as e:
        print(f"Erreur inattendue: {e}")
        return None

def call_claude_api(full_prompt):
    """
    Appelle l'API OpenRouter avec le prompt complet

    Args:
        full_prompt (str): Le prompt complet

    Returns:
        dict: Résultat de l'analyse JSON
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "anthropic/claude-sonnet-4",
        "messages": [
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1000
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        # Vérifier le statut
        response.raise_for_status()
        
        # Extraire la réponse
        result_data = response.json()
        result_text = result_data["choices"][0]["message"]["content"].strip()
        
        # Nettoyer et parser le JSON
        if result_text.startswith('```json'):
            result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Parser le JSON
        analysis_result = json.loads(result_text)
        
        return analysis_result

    except requests.exceptions.Timeout:
        print("Erreur: La requête a expiré.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erreur API: {e}")
        print(f"Payload envoyé: {payload}")
        return None
    except json.JSONDecodeError as e:
        print(f"Erreur JSON: {e}")
        print(f"Réponse brute: {response.text if response else 'Aucune réponse'}")
        return None
    except Exception as e:
        print(f"Erreur inattendue: {e}")
        return None

def analyze_vb6_with_tech_prompt(file_path):
    """
    Analyse un fichier VB6 avec le prompt technique VB6_TECH_PROMPT

    Args:
        file_path (str): Chemin vers le fichier VB6

    Returns:
        dict: Résultat de l'analyse JSON
    """
    from vb6_prompts import VB6_TECH_PROMPT

    vb6_code = read_vb6_file(file_path)
    full_prompt = build_full_prompt(VB6_TECH_PROMPT, vb6_code)
    return call_deepseek_api(full_prompt)

def analyze_vb6_with_human_prompt(file_path):
    """
    Analyse un fichier VB6 avec le prompt humain VB6_HUMAN_PROMPT

    Args:
        file_path (str): Chemin vers le fichier VB6

    Returns:
        dict: Résultat de l'analyse JSON
    """
    from vb6_prompts import VB6_HUMAN_PROMPT

    vb6_code = read_vb6_file(file_path)
    full_prompt = build_full_prompt(VB6_HUMAN_PROMPT, vb6_code)
    return call_deepseek_api(full_prompt)