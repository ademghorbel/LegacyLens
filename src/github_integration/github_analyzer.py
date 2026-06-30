"""Module pour analyser les projets GitHub."""

import os
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

# Import absolu au lieu de relatif
from agent.graph import create_graph, State
from .github_cloner import GitHubCloner


class GitHubAnalyzer:
    """Classe pour analyser les projets GitHub avec le système multi-agent."""
    
    def __init__(self, github_token: Optional[str] = None):
        """Initialiser l'analyseur GitHub.
        
        Args:
            github_token: Token d'accès GitHub pour les dépôts privés
        """
        self.github_token = github_token
        self.cloner = GitHubCloner(github_token)
    
    async def analyze_github_repository(
        self, 
        github_url: str, 
        branch: Optional[str] = None,
        max_files: int = 20,
        include_tests: bool = False,
        verbose_mode: bool = True
    ) -> Dict[str, Any]:
        """Analyser un dépôt GitHub.
        
        Args:
            github_url: URL du dépôt GitHub
            branch: Branche à analyser (optionnel)
            max_files: Nombre maximum de fichiers à analyser
            include_tests: Inclure les fichiers de test
            verbose_mode: Mode verbeux
            
        Returns:
            Résultats de l'analyse
            
        Raises:
            ValueError: Si l'URL est invalide ou le clonage échoue
        """
        repo_path = None
        
        try:
            # Cloner le dépôt
            repo_path = self.cloner.clone_repository(github_url, branch)
            
            # Analyser le projet cloné
            results = await self._analyze_local_project(
                repo_path, max_files, include_tests, verbose_mode
            )
            
            # Ajouter les métadonnées GitHub
            results['github_metadata'] = {
                'github_url': github_url,
                'branch': branch,
                'cloned_path': repo_path
            }
            
            return results
            
        except Exception as e:
            # Nettoyer en cas d'erreur
            if repo_path and os.path.exists(repo_path):
                self.cloner.cleanup()
            raise e
    
    async def _analyze_local_project(
        self, 
        project_path: str, 
        max_files: int = 20,
        include_tests: bool = False,
        verbose_mode: bool = True
    ) -> Dict[str, Any]:
        """Analyser un projet local avec le système multi-agent.
        
        Args:
            project_path: Chemin vers le projet
            max_files: Nombre maximum de fichiers à analyser
            include_tests: Inclure les fichiers de test
            verbose_mode: Mode verbeux
            
        Returns:
            Résultats de l'analyse
        """
        # Initialiser le graphe
        graph = create_graph()
        
        # État initial
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
            functionality_analyses=[]
        )
        
        # Configuration
        config = {
            "configurable": {
                "project_path": project_path,
                "max_files": max_files,
                "include_tests": include_tests,
                "verbose": verbose_mode
            }
        }
        
        # Exécuter l'analyse
        if verbose_mode:
            print(f"🔍 Analyse du projet: {project_path}")
        
        result = await graph.ainvoke(initial_state, config)
        
        return result
    
    def cleanup(self):
        """Nettoyer les répertoires temporaires."""
        try:
            self.cloner.cleanup()
        except Exception as e:
            print(f"⚠️ Erreur lors du nettoyage standard: {e}")
            # Essayer un nettoyage forcé
            try:
                self.cloner.force_cleanup_all()
            except Exception as e2:
                print(f"❌ Échec du nettoyage forcé: {e2}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit avec nettoyage automatique."""
        self.cleanup() 