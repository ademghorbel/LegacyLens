"""
Language Identifier Agent - Détecte les langages de programmation dans les fichiers.

Cet agent utilise plusieurs méthodes de détection :
- Analyse statique (extensions, shebangs, patterns)
- Analyse LLM avec LangChain et Gemini
- Framework detection
- Confidence scoring
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import mimetypes

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

from ..base_agent import BaseAgent, AgentConfig, AgentResult, AgentStatus, AgentMetadata
from ...core.types import LanguageType, LanguageDetectionResult, FileInfo
from ...core.logging_manager import get_logger

# Import des modules spécifiques à l'agent
from .config import get_language_identifier_config, LanguageIdentifierConfig
from .prompts import LanguageIdentifierPrompts
from .schemas import LanguageAnalysis, FileAnalysisInput, ProjectAnalysisInput, AgentResponse, ProjectLanguageStats
from .tools import (
    FileAnalysisTools, StaticAnalyzer, ContentAnalyzer, KeywordDetector, FrameworkDetector,
    detect_language_by_extension, detect_language_by_shebang, detect_language_by_keywords
)


class LanguageIdentifierAgent(BaseAgent):
    """
    Agent spécialisé dans l'identification des langages de programmation.
    
    Utilise une approche multi-méthodes pour détecter avec précision
    le langage de programmation utilisé dans chaque fichier:
    - Analyse statique (extensions, shebangs, patterns)
    - Analyse LLM avec LangChain et Gemini
    - Détection de frameworks
    - Scoring de confiance
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialise l'agent avec sa configuration."""
        if config is None:
            config = AgentConfig(
                name="language_identifier",
                version="2.0.0",
                description="Identifies programming languages using static analysis and LLM",
                timeout=60,
                retry_count=2
            )
        
        super().__init__(config)
        self.logger = get_logger("agent.language_identifier")
        
        # Chargement de la configuration spécifique
        self.agent_config: LanguageIdentifierConfig = get_language_identifier_config()
        
        # Initialisation des composants
        self.prompts = LanguageIdentifierPrompts()
        self.file_analyzer = FileAnalysisTools()
        self.static_analyzer = StaticAnalyzer()
        self.content_analyzer = ContentAnalyzer()
        self.keyword_detector = KeywordDetector()
        self.framework_detector = FrameworkDetector()
        
        # Statistiques
        self.processed_files = 0
        self.successful_analyses = 0
        
        self.logger.info(
            "LanguageIdentifierAgent initialized",
            llm_enabled=self.agent_config.enable_llm_analysis,
            model=self.agent_config.llm_model
        )
    
    async def process(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Traite les fichiers d'entrée pour identifier les langages avec LLM.
        
        Args:
            input_data: Dict contenant 'files' (liste de chemins) ou 'project_path'
            
        Returns:
            AgentResult avec les détections de langages
        """
        start_time = datetime.utcnow()
        self.status = AgentStatus.PROCESSING
        
        try:
            # Validation de l'entrée
            if not self.validate_input(input_data):
                raise ValueError("Invalid input data format")
            
            # Extraction des fichiers à analyser
            files_to_analyze = self._extract_files(input_data)
            
            if not files_to_analyze:
                raise ValueError("No files provided for analysis")
            
            self.logger.info(
                f"Starting language identification",
                files_count=len(files_to_analyze),
                llm_enabled=self.agent_config.enable_llm_analysis
            )
            
            results = []
            errors = []
            
            for file_path in files_to_analyze:
                try:
                    # Analyse complète du fichier avec LLM
                    detection_result = await self._analyze_file_with_llm(file_path)
                    results.append(detection_result.dict())
                    self.successful_analyses += 1
                    
                    self.logger.debug(
                        "Language detected",
                        file=str(file_path),
                        language=detection_result.detected_language,
                        confidence=detection_result.confidence_score,
                        frameworks=detection_result.frameworks_detected or []
                    )
                    
                except Exception as e:
                    error_msg = f"Failed to analyze {file_path}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
                
                self.processed_files += 1
            
            # Compilation des statistiques
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            project_stats = self._compile_project_statistics(results, execution_time)
            
            # Création de la réponse
            response_data = AgentResponse(
                success=True,
                files_analyzed=self.processed_files,
                files_failed=len(errors),
                detections=results,
                statistics=project_stats,
                warnings=errors
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.status = AgentStatus.COMPLETED
            
            return AgentResult(
                agent_id=self.agent_id,
                agent_name=self.config.name,
                status=AgentStatus.COMPLETED,
                data=response_data.dict(),
                metadata=AgentMetadata(
                    agent_name=self.config.name,
                    version=self.config.version,
                    execution_id=self.agent_id,
                    timestamp=datetime.utcnow()
                ),
                execution_time=execution_time,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.error(f"Agent processing failed: {e}")
            
            return AgentResult(
                agent_id=self.agent_id,
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                data={"error": str(e)},
                metadata=AgentMetadata(
                    agent_name=self.config.name,
                    version=self.config.version,
                    execution_id=self.agent_id,
                    timestamp=datetime.utcnow()
                ),
                execution_time=execution_time,
                timestamp=datetime.utcnow(),
                error_message=str(e)
            )
    
    def _extract_files(self, input_data: Dict[str, Any]) -> List[Path]:
        """Extrait la liste des fichiers à analyser depuis les données d'entrée."""
        files = []
        
        if "files" in input_data:
            # Liste directe de fichiers
            files = [Path(f) for f in input_data["files"]]
        elif "project_path" in input_data:
            # Scan d'un projet complet
            project_path = Path(input_data["project_path"])
            if project_path.is_dir():
                files = self._scan_project_files(project_path)
            else:
                files = [project_path]
        
        # Filtrer les fichiers existants
        return [f for f in files if f.exists() and f.is_file()]
    
    def _scan_project_files(self, project_path: Path) -> List[Path]:
        """Scanne récursivement les fichiers d'un projet."""
        files = []
        
        # Extensions à ignorer
        ignore_extensions = {'.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.bin'}
        ignore_dirs = {'.git', '.svn', '.hg', '__pycache__', 'node_modules', '.venv', 'venv'}
        
        for file_path in project_path.rglob('*'):
            if (file_path.is_file() 
                and file_path.suffix not in ignore_extensions
                and not any(part in ignore_dirs for part in file_path.parts)):
                files.append(file_path)
        
        return files
    
    async def _analyze_file(self, file_path: Path) -> LanguageDetectionResult:
        """Analyse un fichier individuel pour déterminer son langage."""
        
        # Méthodes de détection avec scores
        detection_methods = []
        scores = {}
        
        # 1. Détection par extension
        extension_language = self._detect_by_extension(file_path)
        if extension_language != LanguageType.UNKNOWN:
            scores[extension_language] = scores.get(extension_language, 0) + 0.8
            detection_methods.append("extension")
        
        # 2. Détection par contenu (si fichier text)
        if self._is_text_file(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(8192)  # Lire les premiers 8KB
                
                # Détection par shebang
                shebang_language = self._detect_by_shebang(content)
                if shebang_language != LanguageType.UNKNOWN:
                    scores[shebang_language] = scores.get(shebang_language, 0) + 0.9
                    detection_methods.append("shebang")
                
                # Détection par mots-clés
                keyword_scores = self._detect_by_keywords(content)
                for lang, score in keyword_scores.items():
                    scores[lang] = scores.get(lang, 0) + score * 0.6
                    if score > 0:
                        detection_methods.append("keywords")
                
            except Exception as e:
                self.logger.warning(f"Could not read file content for {file_path}: {str(e)}")
        
        # Déterminer le langage principal
        if scores:
            primary_language = max(scores, key=lambda k: scores[k])
            confidence = min(scores[primary_language], 1.0)
            
            # Alternatives (autres langages avec score > 0.3)
            alternatives = [
                {str(lang): score} 
                for lang, score in scores.items() 
                if lang != primary_language and score > 0.3
            ]
        else:
            primary_language = LanguageType.UNKNOWN
            confidence = 0.0
            alternatives = []
        
        return LanguageDetectionResult(
            file_path=str(file_path),
            detected_language=primary_language,
            confidence_score=confidence,
            alternative_languages=alternatives,
            detection_methods=detection_methods,
            metadata={
                "file_size": file_path.stat().st_size,
                "extension": file_path.suffix,
                "encoding": "utf-8"  # Simplifié pour l'instant
            }
        )
    
    def _detect_by_extension(self, file_path: Path) -> LanguageType:
        """Détecte le langage par l'extension du fichier."""
        language_str = detect_language_by_extension(str(file_path))
        try:
            return LanguageType(language_str)
        except ValueError:
            return LanguageType.UNKNOWN
    
    def _detect_by_shebang(self, content: str) -> LanguageType:
        """Détecte le langage par le shebang."""
        language_str = detect_language_by_shebang(content)
        try:
            return LanguageType(language_str)
        except ValueError:
            return LanguageType.UNKNOWN
    
    def _detect_by_keywords(self, content: str) -> Dict[LanguageType, float]:
        """Détecte le langage par analyse des mots-clés."""
        scores_result = detect_language_by_keywords(content)
        
        # Le résultat des outils LangChain peut être une string JSON ou un dict
        if isinstance(scores_result, str):
            try:
                scores_dict = json.loads(scores_result)
            except json.JSONDecodeError:
                return {}
        else:
            scores_dict = scores_result
        
        result = {}
        
        for lang_str, score in scores_dict.items():
            try:
                lang_type = LanguageType(lang_str)
                result[lang_type] = score
            except ValueError:
                continue
                
        return result
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Vérifie si un fichier est un fichier texte."""
        try:
            # Vérifier d'abord que le fichier existe
            if not file_path.exists() or not file_path.is_file():
                return False
                
            # Vérification rapide par extension
            text_extensions = {'.txt', '.md', '.rst', '.py', '.js', '.html', '.css', '.sql', '.yaml', '.json', '.xml'}
            if file_path.suffix.lower() in text_extensions:
                return True
            
            # Vérification par contenu (échantillon)
            with open(file_path, 'rb') as f:
                sample = f.read(1024)
                
            # Vérifier s'il y a des caractères de contrôle (binaire)
            if b'\0' in sample:
                return False
            
            # Essayer de décoder en UTF-8
            try:
                sample.decode('utf-8')
                return True
            except UnicodeDecodeError:
                return False
                
        except Exception:
            return False
    
    def _compile_statistics(self, results: List[Dict]) -> Dict[str, Any]:
        """Compile les statistiques globales de détection."""
        language_counts = {}
        confidence_sum = {}
        total_files = len(results)
        
        for result in results:
            lang = result["detected_language"]
            confidence = result["confidence_score"]
            
            language_counts[lang] = language_counts.get(lang, 0) + 1
            confidence_sum[lang] = confidence_sum.get(lang, 0) + confidence
        
        # Calcul des pourcentages et confiances moyennes
        language_stats = {}
        for lang, count in language_counts.items():
            percentage = (count / total_files) * 100 if total_files > 0 else 0
            avg_confidence = confidence_sum[lang] / count if count > 0 else 0
            
            language_stats[lang] = {
                "file_count": count,
                "percentage": round(percentage, 2),
                "average_confidence": round(avg_confidence, 3)
            }
        
        return {
            "languages": language_stats,
            "total_files": total_files,
            "primary_language": max(language_counts, key=lambda k: language_counts[k]) if language_counts else LanguageType.UNKNOWN
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Valide les données d'entrée."""
        if not isinstance(input_data, dict):
            self.logger.error("Input data must be a dictionary")
            return False
        
        if "files" not in input_data and "project_path" not in input_data:
            self.logger.error("Input must contain either 'files' or 'project_path'")
            return False
        
        if "files" in input_data:
            if not isinstance(input_data["files"], list):
                self.logger.error("'files' must be a list")
                return False
        
        if "project_path" in input_data:
            if not isinstance(input_data["project_path"], (str, Path)):
                self.logger.error("'project_path' must be a string or Path")
                return False
        
        return True
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Retourne les capacités de l'agent."""
        return {
            "name": "Language Identifier",
            "version": self.config.version,
            "description": "Identifies programming languages in source files",
            "supported_languages": [lang.value for lang in LanguageType if lang != LanguageType.UNKNOWN],
            "detection_methods": [
                "file_extension",
                "shebang_analysis", 
                "keyword_analysis",
                "content_heuristics"
            ],
            "input_formats": [
                {"files": "List of file paths to analyze"},
                {"project_path": "Path to project directory for recursive analysis"}
            ],
            "output_format": {
                "detections": "List of LanguageDetectionResult objects",
                "statistics": "Language distribution statistics"
            }
        }

    async def _analyze_file_with_llm(self, file_path: Path) -> LanguageAnalysis:
        """Analyse un fichier avec LLM et méthodes statiques."""
        try:
            # 1. Analyse statique d'abord
            static_analysis = self.file_analyzer.analyze_file_comprehensive(file_path)
            
            if not static_analysis['is_text']:
                # Fichier binaire, retour basé sur l'extension uniquement
                return LanguageAnalysis(
                    file_path=str(file_path),
                    detected_language=static_analysis['language_by_extension'],
                    confidence_score=0.9,
                    detection_methods=["extension"],
                    file_size=static_analysis['size'],
                    analysis_time=0.1,
                    frameworks_detected=[]
                )
            
            # 2. Lecture du contenu pour analyse LLM
            file_content = static_analysis.get('content_sample', '')
            if len(file_content) > self.agent_config.max_content_analysis:
                file_content = file_content[:self.agent_config.max_content_analysis]
            
            # 3. Analyse avec LLM si activée
            llm_result = None
            if self.agent_config.enable_llm_analysis and self.get_llm() and file_content:
                llm_result = await self._analyze_with_llm(file_content, str(file_path))
            
            # 4. Combinaison des résultats
            final_language, final_confidence = self._combine_analysis_results(
                static_analysis, llm_result
            )
            
            # 5. Détection des frameworks
            frameworks = []
            if self.agent_config.enable_framework_detection:
                frameworks = self.framework_detector.detect_frameworks(
                    file_content, LanguageType(final_language)
                )
            
            return LanguageAnalysis(
                file_path=str(file_path),
                detected_language=LanguageType(final_language),
                confidence_score=final_confidence,
                detection_methods=["hybrid_llm_static"],
                file_size=static_analysis['size'],
                analysis_time=0.5,
                frameworks_detected=frameworks
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing file {file_path}: {e}")
            # Fallback sur analyse statique seule
            return LanguageAnalysis(
                file_path=str(file_path),
                detected_language=LanguageType.UNKNOWN,
                confidence_score=0.1,
                detection_methods=["error_fallback"],
                file_size=0,
                analysis_time=0.0,
                frameworks_detected=[]
            )
    
    async def _analyze_with_llm(self, content: str, file_path: str) -> Optional[Dict]:
        """Analyse du contenu avec LLM et outils."""
        try:
            llm = self.get_llm()
            if not llm:
                return None
            
            # Utilisation des outils pour pre-analyse
            extension_result = detect_language_by_extension(file_path)
            shebang_result = detect_language_by_shebang(content)
            keywords_result = detect_language_by_keywords(content)
            
            # Création du prompt enrichi avec les résultats des outils
            tool_analysis = {
                "extension_detection": extension_result,
                "shebang_detection": shebang_result,
                "keywords_scores": keywords_result
            }
            
            identification_prompt = self.prompts.get_identification_prompt(content, file_path)
            
            # Messages pour LangChain avec outils
            messages = [
                self.prompts.create_system_message(
                    "Tu es un expert en identification de langages de programmation. "
                    "Utilise l'analyse statique fournie et le code pour donner une réponse en JSON."
                ),
                ToolMessage(
                    content=f"Analyse statique: {tool_analysis}",
                    tool_call_id="static_analysis"
                ),
                self.prompts.create_human_message(identification_prompt)
            ]
            
            # Appel LLM
            response = await llm.ainvoke(messages)
            
            # Parse de la réponse
            try:
                if hasattr(response, 'content'):
                    content_str = response.content
                else:
                    content_str = str(response)
                
                # Assurer que content_str est une string
                if not isinstance(content_str, str):
                    content_str = str(content_str)
                
                # Extraction du JSON de la réponse
                json_match = re.search(r'\{.*\}', content_str, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    # Enrichir avec les données des outils
                    result['static_analysis'] = tool_analysis
                    return result
                else:
                    self.logger.warning("No JSON found in LLM response")
                    return None
                    
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse LLM response as JSON: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")
            return None
    
    def _combine_analysis_results(self, static_analysis: Dict, llm_result: Optional[Dict]) -> tuple[str, float]:
        """Combine les résultats d'analyse statique et LLM."""
        
        # Scores par méthode
        extension_score = 0.0
        shebang_score = 0.0
        keyword_score = 0.0
        llm_score = 0.0
        
        # Language candidats
        candidates = {}
        
        # 1. Score par extension
        ext_lang = static_analysis.get('language_by_extension', LanguageType.UNKNOWN)
        if ext_lang != LanguageType.UNKNOWN:
            candidates[ext_lang.value] = self.agent_config.extension_weight
            extension_score = self.agent_config.extension_weight
        
        # 2. Score par shebang
        shebang_lang = static_analysis.get('language_by_shebang', LanguageType.UNKNOWN)
        if shebang_lang != LanguageType.UNKNOWN:
            candidates[shebang_lang.value] = candidates.get(shebang_lang.value, 0) + self.agent_config.shebang_weight
            shebang_score = self.agent_config.shebang_weight
        
        # 3. Score par mots-clés
        keyword_scores = static_analysis.get('keyword_scores', {})
        if keyword_scores:
            best_keyword_lang = max(keyword_scores.keys(), key=lambda k: keyword_scores[k])
            keyword_confidence = keyword_scores[best_keyword_lang]
            weighted_keyword_score = keyword_confidence * self.agent_config.keyword_weight
            candidates[best_keyword_lang.value] = candidates.get(best_keyword_lang.value, 0) + weighted_keyword_score
            keyword_score = weighted_keyword_score
        
        # 4. Score LLM
        if llm_result and 'language' in llm_result:
            llm_lang = llm_result['language']
            llm_confidence = llm_result.get('confidence', 0.5)
            weighted_llm_score = llm_confidence * self.agent_config.llm_weight
            candidates[llm_lang] = candidates.get(llm_lang, 0) + weighted_llm_score
            llm_score = weighted_llm_score
        
        # Choix du meilleur candidat
        if candidates:
            best_language = max(candidates.keys(), key=lambda k: candidates[k])
            final_confidence = min(candidates[best_language], 1.0)
        else:
            best_language = LanguageType.UNKNOWN.value
            final_confidence = 0.1
        
        self.logger.debug(
            "Analysis combination",
            extension_score=extension_score,
            shebang_score=shebang_score,
            keyword_score=keyword_score,
            llm_score=llm_score,
            final_language=best_language,
            final_confidence=final_confidence
        )
        
        return best_language, final_confidence

    def _compile_project_statistics(self, results: List[Dict], analysis_duration: float) -> Optional[ProjectLanguageStats]:
        """Compile les statistiques du projet."""
        try:
            if not results:
                return None
            
            # Comptage des langages
            language_counts = {}
            file_type_counts = {}
            
            for result in results:
                lang = result.get('detected_language')
                if lang:
                    if lang not in language_counts:
                        language_counts[lang] = {'files': 0, 'confidence_sum': 0.0}
                    language_counts[lang]['files'] += 1
                    language_counts[lang]['confidence_sum'] += result.get('confidence_score', 0.0)
                
                # Comptage des extensions
                file_path = result.get('file_path', '')
                if file_path:
                    ext = Path(file_path).suffix.lower()
                    if ext:
                        file_type_counts[ext] = file_type_counts.get(ext, 0) + 1
            
            # Détermination du langage principal
            primary_language = None
            if language_counts:
                primary_language = max(language_counts.keys(), 
                                     key=lambda k: language_counts[k]['files'])
                primary_language = LanguageType(primary_language)
            
            # Construction des statistiques par langage
            languages_stats = {}
            for lang, stats in language_counts.items():
                try:
                    lang_enum = LanguageType(lang)
                    languages_stats[lang_enum] = {
                        'files': stats['files'],
                        'percentage': (stats['files'] / len(results)) * 100,
                        'avg_confidence': stats['confidence_sum'] / stats['files']
                    }
                except (ValueError, KeyError):
                    # Skip invalid language types
                    continue
            
            return ProjectLanguageStats(
                total_files=len(results),
                languages=languages_stats,
                primary_language=primary_language,
                file_types=file_type_counts,
                analysis_duration=analysis_duration
            )
            
        except Exception as e:
            self.logger.error(f"Error compiling project statistics: {e}")
            return None
