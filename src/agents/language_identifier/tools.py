"""
Tools for language identification agent.

Implements utility functions and tools for static analysis, content analysis,
and external parser integration for language detection.
"""

import os
import re
import ast
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import chardet

from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

from ...core.types import LanguageType
from ...core.logging_manager import get_logger

logger = get_logger("agent.language_identifier.tools")


# Extensions de fichiers par langage
EXTENSIONS_MAP = {
    LanguageType.PYTHON: {'.py', '.pyw', '.py3', '.pyi', '.pyc', '.ipynb'},
    LanguageType.JAVASCRIPT: {'.js', '.mjs', '.jsx'},
    LanguageType.TYPESCRIPT: {'.ts', '.tsx', '.d.ts'},
    LanguageType.JAVA: {'.java', '.class', '.jar'},
    LanguageType.CSHARP: {'.cs', '.csx'},
    LanguageType.CPP: {'.cpp', '.cxx', '.cc', '.hpp', '.hxx', '.h++'},
    LanguageType.C: {'.c', '.h'},
    LanguageType.GO: {'.go'},
    LanguageType.RUST: {'.rs'},
    LanguageType.PHP: {'.php', '.phtml', '.php3', '.php4', '.php5'},
    LanguageType.RUBY: {'.rb', '.rbw', '.rake', '.gemspec'},
    LanguageType.SQL: {'.sql', '.ddl', '.dml'},
    LanguageType.HTML: {'.html', '.htm', '.xhtml'},
    LanguageType.CSS: {'.css', '.scss', '.sass', '.less'},
    LanguageType.SHELL: {'.sh', '.bash', '.zsh', '.fish', '.ksh'},
    LanguageType.YAML: {'.yaml', '.yml'},
    LanguageType.JSON: {'.json', '.jsonl'},
    LanguageType.XML: {'.xml', '.xsd', '.xsl', '.xslt'},
}

# Shebangs caractéristiques
SHEBANGS_MAP = {
    LanguageType.PYTHON: [
        r'#!/usr/bin/env python',
        r'#!/usr/bin/python',
        r'#!/usr/local/bin/python',
        r'#!\s*/usr/bin/python\d*'
    ],
    LanguageType.SHELL: [
        r'#!/bin/bash',
        r'#!/bin/sh',
        r'#!/usr/bin/env bash',
        r'#!/bin/zsh'
    ],
    LanguageType.JAVASCRIPT: [
        r'#!/usr/bin/env node',
        r'#!/usr/bin/node'
    ],
    LanguageType.PHP: [
        r'#!/usr/bin/env php',
        r'#!/usr/bin/php'
    ],
    LanguageType.RUBY: [
        r'#!/usr/bin/env ruby',
        r'#!/usr/bin/ruby'
    ]
}

# Mots-clés et patterns caractéristiques
KEYWORDS_MAP = {
    LanguageType.PYTHON: [
        r'\bimport\s+\w+', r'\bfrom\s+\w+\s+import',
        r'\bdef\s+\w+\s*\(', r'\bclass\s+\w+\s*\(',
        r'__name__\s*==\s*["\']__main__["\']',
        r'\bif\s+__name__\s*==',
        r'print\s*\(', r'len\s*\('
    ],
    LanguageType.JAVASCRIPT: [
        r'\bfunction\s+\w+\s*\(', r'\bvar\s+\w+\s*=',
        r'\blet\s+\w+\s*=', r'\bconst\s+\w+\s*=',
        r'console\.log\s*\(', r'require\s*\(',
        r'module\.exports\s*=', r'=>',
        r'\$\{.*\}', r'document\.'
    ],
    LanguageType.JAVA: [
        r'\bpublic\s+class\s+\w+', r'\bprivate\s+\w+',
        r'\bpublic\s+static\s+void\s+main',
        r'\bimport\s+java\.', r'\bSystem\.out\.print',
        r'\bString\[\]\s+args', r'\bnew\s+\w+\s*\('
    ],
    LanguageType.CSHARP: [
        r'\busing\s+System', r'\bnamespace\s+\w+',
        r'\bpublic\s+class\s+\w+', r'\bConsole\.Write',
        r'\bstatic\s+void\s+Main', r'\[.*Attribute.*\]'
    ],
    LanguageType.CPP: [
        r'#include\s*<.*>', r'#include\s*".*"',
        r'\bstd::', r'\bcout\s*<<', r'\bcin\s*>>',
        r'\busing\s+namespace\s+std',
        r'\bint\s+main\s*\('
    ],
    LanguageType.PHP: [
        r'<\?php', r'<\?\s', r'\$\w+\s*=',
        r'\becho\s+', r'\bprint\s+',
        r'\bfunction\s+\w+\s*\(', r'->'
    ],
    LanguageType.RUBY: [
        r'\bdef\s+\w+', r'\bend\b',
        r'\bclass\s+\w+', r'\brequire\s+',
        r'\bputs\s+', r'\bp\s+',
        r'\.each\s+do', r'@\w+'
    ],
    LanguageType.GO: [
        r'\bpackage\s+main', r'\bfunc\s+main\s*\(',
        r'\bimport\s+\(', r'\bfmt\.',
        r':=', r'\bgo\s+\w+\('
    ],
    LanguageType.RUST: [
        r'\bfn\s+main\s*\(', r'\bfn\s+\w+\s*\(',
        r'\blet\s+mut\s+', r'\blet\s+\w+\s*=',
        r'println!\s*\(', r'\buse\s+std::'
    ]
}


@tool
def detect_language_by_extension(file_path: str) -> str:
    """
    Detect programming language by file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Detected language or "unknown"
    """
    path = Path(file_path)
    extension = path.suffix.lower()
    
    for language, extensions in EXTENSIONS_MAP.items():
        if extension in extensions:
            return language.value
    
    return LanguageType.UNKNOWN.value


@tool
def detect_language_by_shebang(content: str) -> str:
    """
    Detect programming language by shebang line.
    
    Args:
        content: File content to analyze
        
    Returns:
        Detected language or "unknown"
    """
    lines = content.split('\n', 2)
    if not lines or not lines[0].startswith('#!'):
        return LanguageType.UNKNOWN.value
    
    shebang = lines[0]
    
    for language, patterns in SHEBANGS_MAP.items():
        for pattern in patterns:
            if re.search(pattern, shebang):
                return language.value
    
    return LanguageType.UNKNOWN.value


@tool
def detect_language_by_keywords(content: str) -> dict:
    """
    Detect programming language by analyzing keywords and patterns.
    
    Args:
        content: File content to analyze
        
    Returns:
        Dictionary with language scores
    """
    scores = {}
    
    for language, patterns in KEYWORDS_MAP.items():
        score = 0
        matches = 0
        
        for pattern in patterns:
            pattern_matches = len(re.findall(pattern, content, re.MULTILINE))
            if pattern_matches > 0:
                matches += 1
                score += min(pattern_matches, 5) * 0.1  # Max 0.5 par pattern
        
        if matches > 0:
            # Score basé sur le nombre de patterns matchés et leur fréquence
            scores[language.value] = min(score, 1.0)
    
    return scores


class StaticAnalyzer:
    """Static analysis tools for language detection."""
    
    @staticmethod
    def detect_by_extension(file_path: Path) -> LanguageType:
        """Detect language by file extension."""
        extension_map = {
            '.py': LanguageType.PYTHON,
            '.pyx': LanguageType.PYTHON,
            '.pyi': LanguageType.PYTHON,
            '.js': LanguageType.JAVASCRIPT,
            '.jsx': LanguageType.JAVASCRIPT,
            '.ts': LanguageType.TYPESCRIPT,
            '.tsx': LanguageType.TYPESCRIPT,
            '.java': LanguageType.JAVA,
            '.kt': LanguageType.UNKNOWN,  # Kotlin -> Unknown for now
            '.cpp': LanguageType.CPP,
            '.cxx': LanguageType.CPP,
            '.cc': LanguageType.CPP,
            '.c': LanguageType.C,
            '.h': LanguageType.C,
            '.hpp': LanguageType.CPP,
            '.cs': LanguageType.CSHARP,
            '.go': LanguageType.GO,
            '.rs': LanguageType.RUST,
            '.php': LanguageType.PHP,
            '.rb': LanguageType.RUBY,
            '.swift': LanguageType.UNKNOWN,  # Swift -> Unknown for now
            '.sh': LanguageType.SHELL,
            '.bash': LanguageType.SHELL,
            '.zsh': LanguageType.SHELL,
            '.ps1': LanguageType.UNKNOWN,  # PowerShell -> Unknown for now
            '.sql': LanguageType.SQL,
            '.html': LanguageType.HTML,
            '.htm': LanguageType.HTML,
            '.css': LanguageType.CSS,
            '.scss': LanguageType.CSS,
            '.sass': LanguageType.CSS,
            '.json': LanguageType.JSON,
            '.xml': LanguageType.XML,
            '.yaml': LanguageType.YAML,
            '.yml': LanguageType.YAML,
            '.md': LanguageType.UNKNOWN,  # Markdown -> Unknown for now
            '.dockerfile': LanguageType.UNKNOWN,  # Dockerfile -> Unknown for now
        }
        
        suffix = file_path.suffix.lower()
        return extension_map.get(suffix, LanguageType.UNKNOWN)
    
    @staticmethod
    def detect_by_shebang(content: str) -> LanguageType:
        """Detect language by shebang line."""
        if not content.startswith('#!'):
            return LanguageType.UNKNOWN
        
        first_line = content.split('\n')[0].lower()
        
        shebang_patterns = {
            'python': LanguageType.PYTHON,
            'node': LanguageType.JAVASCRIPT,
            'bash': LanguageType.SHELL,
            'sh': LanguageType.SHELL,
            'zsh': LanguageType.SHELL,
            'ruby': LanguageType.RUBY,
            'php': LanguageType.PHP,
            'perl': LanguageType.UNKNOWN,  # Could add PERL if needed
        }
        
        for pattern, language in shebang_patterns.items():
            if pattern in first_line:
                return language
        
        return LanguageType.UNKNOWN


class ContentAnalyzer:
    """Content-based analysis tools."""
    
    @staticmethod
    def detect_encoding(file_path: Path) -> str:
        """Detect file encoding."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # Read first 10KB
            result = chardet.detect(raw_data)
            return result.get('encoding', 'utf-8') or 'utf-8'
        except Exception:
            return 'utf-8'
    
    @staticmethod
    def is_text_file(file_path: Path) -> bool:
        """Check if file is a text file."""
        try:
            # First check if file exists
            if not file_path.exists():
                return False
                
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type and mime_type.startswith('text/'):
                return True
            
            # Check by content for files without clear MIME type
            encoding = ContentAnalyzer.detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                sample = f.read(1024)
            
            # Check for binary content
            if '\x00' in sample:
                return False
            
            # Check if mostly printable characters
            if len(sample) == 0:
                return True  # Empty file is considered text
            printable_ratio = sum(1 for c in sample if c.isprintable() or c.isspace()) / len(sample)
            return printable_ratio > 0.7
            
        except Exception:
            return False
    
    @staticmethod
    def extract_imports(content: str, language: LanguageType) -> List[str]:
        """Extract import statements based on language."""
        imports = []
        
        if language == LanguageType.PYTHON:
            # Python imports
            import_patterns = [
                r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)',
                r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\s+import',
            ]
        elif language == LanguageType.JAVASCRIPT:
            # JavaScript imports
            import_patterns = [
                r"^\s*import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
                r"^\s*const\s+.*\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
                r"^\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            ]
        elif language == LanguageType.JAVA:
            # Java imports
            import_patterns = [
                r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_\.]*);?',
            ]
        else:
            return imports
        
        for line in content.split('\n'):
            for pattern in import_patterns:
                match = re.match(pattern, line, re.MULTILINE)
                if match:
                    imports.append(match.group(1))
        
        return imports


class KeywordDetector:
    """Keyword-based language detection."""
    
    LANGUAGE_KEYWORDS = {
        LanguageType.PYTHON: {
            'def', 'class', 'import', 'from', 'if', 'elif', 'else', 'for', 'while',
            'try', 'except', 'finally', 'with', 'as', 'lambda', 'yield', 'async',
            'await', 'nonlocal', 'global', '__init__', '__name__', '__main__'
        },
        LanguageType.JAVASCRIPT: {
            'function', 'var', 'let', 'const', 'class', 'extends', 'import', 'export',
            'default', 'async', 'await', 'promise', 'console', 'document', 'window',
            'require', 'module', 'exports', 'typeof', 'instanceof'
        },
        LanguageType.JAVA: {
            'public', 'private', 'protected', 'class', 'interface', 'extends', 'implements',
            'import', 'package', 'static', 'final', 'abstract', 'synchronized', 'volatile',
            'System', 'String', 'ArrayList', 'HashMap'
        },
        LanguageType.CPP: {
            '#include', '#define', '#ifdef', '#ifndef', 'using', 'namespace', 'class',
            'struct', 'template', 'typename', 'virtual', 'override', 'const', 'static',
            'std::', 'cout', 'cin', 'endl'
        },
        LanguageType.GO: {
            'package', 'import', 'func', 'var', 'const', 'type', 'struct', 'interface',
            'go', 'defer', 'select', 'channel', 'goroutine', 'fmt.', 'range'
        }
    }
    
    @staticmethod
    def analyze_keywords(content: str) -> Dict[LanguageType, float]:
        """Analyze content for language-specific keywords."""
        scores = {}
        content_lower = content.lower()
        
        for language, keywords in KeywordDetector.LANGUAGE_KEYWORDS.items():
            matches = 0
            total_keywords = len(keywords)
            
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    matches += 1
            
            if total_keywords > 0:
                scores[language] = matches / total_keywords
        
        return scores


class FrameworkDetector:
    """Detect frameworks and libraries."""
    
    FRAMEWORK_PATTERNS = {
        # Python frameworks
        'django': [r'from django', r'import django', r'DJANGO_SETTINGS_MODULE'],
        'flask': [r'from flask', r'import flask', r'Flask\(__name__\)'],
        'fastapi': [r'from fastapi', r'import fastapi', r'FastAPI\('],
        'pandas': [r'import pandas', r'pd\.DataFrame'],
        'numpy': [r'import numpy', r'np\.array'],
        
        # JavaScript frameworks
        'react': [r'import.*react', r'from.*react', r'React\.Component', r'useState', r'useEffect'],
        'vue': [r'import.*vue', r'Vue\.component', r'new Vue'],
        'angular': [r'@Component', r'@Injectable', r'import.*@angular'],
        'express': [r'require.*express', r'express\(\)', r'app\.get'],
        'jquery': [r'\$\(', r'jQuery\('],
        
        # Java frameworks
        'spring': [r'@SpringBootApplication', r'@RestController', r'@Service', r'@Autowired'],
        'hibernate': [r'@Entity', r'@Table', r'@Column', r'SessionFactory'],
    }
    
    @staticmethod
    def detect_frameworks(content: str, language: LanguageType) -> List[str]:
        """Detect frameworks in content."""
        detected = []
        
        for framework, patterns in FrameworkDetector.FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                    if framework not in detected:
                        detected.append(framework)
                    break
        
        return detected


class FileAnalysisTools:
    """High-level file analysis tools."""
    
    @staticmethod
    def analyze_file_comprehensive(file_path: Path) -> Dict:
        """Perform comprehensive file analysis."""
        result = {
            'path': str(file_path),
            'exists': file_path.exists(),
            'size': 0,
            'is_text': False,
            'encoding': 'unknown',
            'language_by_extension': LanguageType.UNKNOWN,
            'language_by_shebang': LanguageType.UNKNOWN,
            'keyword_scores': {},
            'imports': [],
            'frameworks': [],
            'content_sample': '',
        }
        
        if not file_path.exists():
            return result
        
        try:
            result['size'] = file_path.stat().st_size
            result['is_text'] = ContentAnalyzer.is_text_file(file_path)
            
            if not result['is_text']:
                return result
            
            result['encoding'] = ContentAnalyzer.detect_encoding(file_path)
            result['language_by_extension'] = StaticAnalyzer.detect_by_extension(file_path)
            
            # Read content for analysis
            with open(file_path, 'r', encoding=result['encoding'], errors='ignore') as f:
                content = f.read()
            
            result['content_sample'] = content[:500]  # First 500 chars
            result['language_by_shebang'] = StaticAnalyzer.detect_by_shebang(content)
            result['keyword_scores'] = KeywordDetector.analyze_keywords(content)
            
            # Get best language guess for imports and frameworks
            best_language = result['language_by_extension']
            if best_language == LanguageType.UNKNOWN and result['keyword_scores']:
                best_language = max(result['keyword_scores'].keys(), key=lambda k: result['keyword_scores'][k])
            
            result['imports'] = ContentAnalyzer.extract_imports(content, best_language)
            result['frameworks'] = FrameworkDetector.detect_frameworks(content, best_language)
            
        except Exception as e:
            logger.warning(f"Error analyzing file {file_path}: {e}")
        
        return result
