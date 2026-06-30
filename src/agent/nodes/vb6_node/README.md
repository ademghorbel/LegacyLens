# VB6 Node avec Gemini LLM - Documentation

## Vue d'ensemble

Le VB6 Node a été amélioré pour utiliser le modèle Gemini de Google avec des outils spécialisés pour analyser le code VB6. Cette version avancée fournit une analyse approfondie du code legacy VB6.

## Fonctionnalités

### 🧠 LLM Gemini Integration
- Utilise le modèle `gemini-1.5-pro` pour l'analyse de code
- Prompt système spécialisé pour l'analyse VB6
- Gestion d'erreurs robuste avec fallback

### 🛠️ Outils Spécialisés

#### 1. `extract_vb6_subroutines`
- Extrait toutes les subroutines et fonctions du code VB6
- Identifie les modificateurs d'accès (Public, Private, Friend)
- Retourne le code complet avec les numéros de ligne

#### 2. `extract_vb6_forms`
- Analyse les formulaires VB6 et leurs contrôles
- Identifie les types de contrôles (Button, TextBox, etc.)
- Mappe la structure UI de l'application

#### 3. `extract_vb6_modules`
- Détermine le type de module (Form, Module, Class)
- Extrait les attributs et déclarations de variables
- Analyse la structure générale du module

#### 4. `analyze_vb6_dependencies`
- Identifie les références externes
- Trouve les appels API Windows
- Mappe les dépendances d'objets

#### 5. `count_vb6_complexity`
- Calcule les métriques de complexité
- Compte les lignes de code, boucles, conditions
- Évalue la complexité structurelle

## Configuration

### 1. Variables d'environnement
```bash
# Fichier .env
GOOGLE_API_KEY=votre_clé_api_google
GEMINI_MODEL=gemini-1.5-pro
GEMINI_TEMPERATURE=0.1
```

### 2. Obtenir une clé API Google
1. Visitez [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Créez une nouvelle clé API
3. Ajoutez-la à votre fichier `.env`

## Résultats d'analyse

Le node retourne un objet avec :
- `llm_analysis` : Analyse détaillée par Gemini
- `tools_used` : Liste des outils utilisés
- `file_size` : Taille du fichier analysé
- `processing_status` : Statut du traitement

### Exemple de sortie
```python
{
    "file_path": "/path/to/file.vb",
    "node_type": "vb6_node_advanced",
    "language": "vb6",
    "processing_status": "completed",
    "message": "VB6 file analyzed with Gemini LLM",
    "llm_analysis": "...", # Analyse détaillée
    "tools_used": ["extract_vb6_subroutines", "..."],
    "file_size": 2048,
    "original_info": {...}
}
```

## Gestion d'erreurs

### Fallback automatique
Si l'API Gemini échoue ou n'est pas configurée :
- Traitement simple sans LLM
- Statut `completed_with_fallback`
- Message d'erreur descriptif

### Types d'erreurs gérées
- Clé API manquante
- Fichier non trouvé
- Erreurs de lecture de fichier
- Erreurs d'API Gemini

## Bonnes pratiques

### 1. Optimisation des tokens
- Limite le code à 10,000 caractères pour éviter les limites
- Focus sur les parties les plus importantes du code

### 2. Configuration LLM
- Température basse (0.1) pour des analyses cohérentes
- Modèle `gemini-1.5-pro` pour de meilleures performances

### 3. Monitoring
- Logs détaillés pour le debugging
- Métriques de performance incluses

## Cas d'usage

### Reverse Engineering
- Analyse de code legacy VB6
- Documentation automatique
- Identification des patterns

### Migration
- Évaluation de la complexité de migration
- Identification des dépendances critiques
- Recommandations de modernisation

### Audit de code
- Détection de problèmes de sécurité
- Identification de la dette technique
- Analyse de la qualité du code

## Exemple d'utilisation

```python
# Le node est appelé automatiquement par le pipeline
# avec les fichiers VB6 détectés
state = {
    "files_to_process_with_vb6": [
        {
            "file_path": "/path/to/legacy.vb",
            "filename": "legacy.vb",
            "language": "vb6"
        }
    ]
}

result = await vb6_node(state, config)
print(result["processed_files"][0]["llm_analysis"])
```
