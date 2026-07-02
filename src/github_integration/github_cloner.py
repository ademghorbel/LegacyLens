"""Module pour cloner les dépôts GitHub."""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple
import re
import time

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitHubCloner:
    """Classe pour cloner et gérer les dépôts GitHub."""
    
    def __init__(self, github_token: Optional[str] = None):
        """Initialiser le cloneur GitHub.
        
        Args:
            github_token: Token d'accès GitHub pour les dépôts privés
        """
        self.github_token = github_token
        self.temp_dirs = []
        
        if not GIT_AVAILABLE:
            raise ImportError(
                "GitPython n'est pas installé. "
                "Installez-le avec: uv add gitpython"
            )
        
        # Créer le dossier tmp sous github_integration
        self.tmp_base_dir = Path(__file__).parent / "tmp"
        self.tmp_base_dir.mkdir(exist_ok=True)
    
    def parse_github_url(self, url: str) -> Tuple[str, str, str]:
        """Parser une URL GitHub pour extraire les informations.
        
        Args:
            url: URL GitHub (https://github.com/owner/repo ou https://github.com/owner/repo.git)
            
        Returns:
            Tuple (owner, repo, branch)
        """
        # Patterns supportés
        patterns = [
            r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/tree/([^/]+)/?$',
            r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/blob/([^/]+)/?$'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                owner = match.group(1)
                repo = match.group(2)
                # ponytail: None = let git pick the repo's real default branch (main/master/other)
                branch = match.group(3) if len(match.groups()) > 2 else None
                return owner, repo, branch
        
        raise ValueError(f"URL GitHub invalide: {url}")
    
    def build_clone_url(self, owner: str, repo: str) -> str:
        """Construire l'URL de clonage avec le token si disponible.
        
        Args:
            owner: Propriétaire du dépôt
            repo: Nom du dépôt
            
        Returns:
            URL de clonage
        """
        if self.github_token:
            return f"https://{self.github_token}@github.com/{owner}/{repo}.git"
        else:
            return f"https://github.com/{owner}/{repo}.git"
    
    def clone_repository(self, github_url: str, branch: Optional[str] = None) -> str:
        """Cloner un dépôt GitHub dans un répertoire temporaire.
        
        Args:
            github_url: URL du dépôt GitHub
            branch: Branche à cloner (optionnel)
            
        Returns:
            Chemin vers le répertoire cloné
            
        Raises:
            ValueError: Si l'URL est invalide
            git.exc.GitCommandError: Si le clonage échoue
        """
        try:
            # Parser l'URL
            owner, repo, default_branch = self.parse_github_url(github_url)
            
            # Utiliser la branche spécifiée ou celle de l'URL
            target_branch = branch or default_branch
            
            # Créer un répertoire temporaire sous github_integration/tmp
            timestamp = int(time.time())
            temp_dir = self.tmp_base_dir / f"github_{owner}_{repo}_{timestamp}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dirs.append(str(temp_dir))
            
            # Construire l'URL de clonage
            clone_url = self.build_clone_url(owner, repo)
            
            print(f"[clone] {owner}/{repo} (branch: {target_branch or 'default'})")
            print(f"[tmp] {temp_dir}")

            # Cloner le dépôt
            repo_path = temp_dir / repo

            # ponytail: omit branch kwarg when unset — git resolves the default branch itself
            clone_kwargs = {"depth": 1}
            if target_branch:
                clone_kwargs["branch"] = target_branch
            git_repo = git.Repo.clone_from(clone_url, repo_path, **clone_kwargs)
            
            # Fermer le repo pour libérer les handles de fichiers
            git_repo.close()
            
            print(f"[ok] cloned to: {repo_path}")
            return str(repo_path)
            
        except git.exc.GitCommandError as e:
            # Nettoyer en cas d'erreur
            if 'temp_dir' in locals():
                self._safe_remove_directory(str(temp_dir))
            
            if "Authentication failed" in str(e):
                raise ValueError(
                    "Échec de l'authentification. "
                    "Vérifiez votre token GitHub ou l'URL du dépôt."
                )
            elif "Repository not found" in str(e):
                raise ValueError(
                    "Dépôt non trouvé. "
                    "Vérifiez l'URL ou les permissions d'accès."
                )
            else:
                raise ValueError(f"Erreur lors du clonage: {e}")
    
    def cleanup(self):
        """Nettoyer tous les répertoires temporaires."""
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    # Essayer de supprimer avec gestion d'erreurs améliorée
                    self._safe_remove_directory(temp_dir)
                    print(f"[cleanup] removed: {temp_dir}")
            except Exception as e:
                print(f"[warn] could not remove {temp_dir}: {e}")
                # Marquer pour suppression ultérieure
                self._mark_for_later_cleanup(temp_dir)
        
        self.temp_dirs.clear()
    
    def _safe_remove_directory(self, directory: str):
        """Supprimer un répertoire de manière sécurisée."""
        # Essayer plusieurs fois avec des délais
        for attempt in range(5):  # Augmenté à 5 tentatives
            try:
                # Sur Windows, essayer de forcer la suppression
                if os.name == 'nt':  # Windows
                    import subprocess
                    try:
                        # Utiliser rmdir /s /q pour forcer la suppression
                        result = subprocess.run(
                            ['rmdir', '/s', '/q', directory], 
                            shell=True, 
                            check=False,
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            print(f"  [ok] rmdir: {directory}")
                            return
                        else:
                            print(f"  [warn] rmdir failed: {result.stderr}")
                    except Exception as e:
                        print(f"  [warn] rmdir error: {e}")
                
                # Méthode standard avec shutil.rmtree
                shutil.rmtree(directory, ignore_errors=True)
                
                # Vérifier si le dossier a été supprimé
                if not os.path.exists(directory):
                    print(f"  [ok] shutil removed: {directory}")
                    return
                else:
                    print(f"  [warn] dir still exists after shutil: {directory}")
                
            except PermissionError as e:
                if attempt < 4:
                    print(f"  [retry {attempt+1}/5] PermissionError, waiting 2s...")
                    time.sleep(2)
                else:
                    print(f"  [error] failed after 5 attempts: {e}")
                    raise
            except Exception as e:
                if attempt < 4:
                    print(f"  [retry {attempt+1}/5] {e}")
                    time.sleep(2)
                else:
                    print(f"  [error] failed after 5 attempts: {e}")
                    raise
    
    def _mark_for_later_cleanup(self, directory: str):
        """Marquer un répertoire pour suppression ultérieure."""
        try:
            # Créer un fichier de marqueur pour suppression ultérieure
            marker_file = os.path.join(directory, ".cleanup_marker")
            with open(marker_file, 'w') as f:
                f.write(f"Marked for cleanup at {time.time()}")
            print(f"  [mark] marked for later cleanup: {directory}")
        except Exception as e:
            print(f"  [error] could not mark for cleanup: {e}")
    
    def force_cleanup_all(self):
        """Forcer le nettoyage de tous les répertoires temporaires."""
        print("[cleanup] forcing removal of all temp dirs...")
        
        for temp_dir in self.temp_dirs[:]:  # Copie de la liste
            try:
                if os.path.exists(temp_dir):
                    # Essayer une suppression plus agressive
                    self._force_remove_directory(temp_dir)
                    print(f"[ok] force-removed: {temp_dir}")
            except Exception as e:
                print(f"[error] could not remove {temp_dir}: {e}")
        
        self.temp_dirs.clear()
    
    def _force_remove_directory(self, directory: str):
        """Supprimer un répertoire de manière forcée."""
        if os.name == 'nt':  # Windows
            try:
                # Essayer avec robocopy (méthode de suppression forcée)
                import subprocess
                temp_dir = os.path.join(os.path.dirname(directory), f"temp_cleanup_{int(time.time())}")
                
                # Créer un répertoire vide et copier vers lui (efface le contenu)
                result = subprocess.run(
                    ['robocopy', temp_dir, directory, '/MIR'], 
                    shell=True, 
                    check=False,
                    capture_output=True,
                    text=True
                )
                
                # Supprimer le répertoire maintenant vide
                if os.path.exists(directory):
                    os.rmdir(directory)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
                return
                
            except Exception as e:
                print(f"  [warn] robocopy failed: {e}")
        
        # Méthode de dernier recours - suppression récursive manuelle
        try:
            for root, dirs, files in os.walk(directory, topdown=False):
                for name in files:
                    try:
                        file_path = os.path.join(root, name)
                        # Changer les permissions
                        os.chmod(file_path, 0o777)
                        os.unlink(file_path)
                    except Exception as e:
                        print(f"    [warn] could not delete file {file_path}: {e}")
                
                for name in dirs:
                    try:
                        dir_path = os.path.join(root, name)
                        # Changer les permissions
                        os.chmod(dir_path, 0o777)
                        os.rmdir(dir_path)
                    except Exception as e:
                        print(f"    [warn] could not delete dir {dir_path}: {e}")
            
            # Supprimer le répertoire racine
            try:
                os.chmod(directory, 0o777)
                os.rmdir(directory)
            except Exception as e:
                print(f"    [warn] could not delete root dir {directory}: {e}")
                
        except Exception as e:
            print(f"  [error] force removal failed: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit avec nettoyage automatique."""
        self.cleanup() 