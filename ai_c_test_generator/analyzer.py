"""
Dependency Analyzer - Analyzes C file dependencies and function relationships
"""

import os
import re
from typing import List, Dict, Set


class DependencyAnalyzer:
    """Analyzes C file dependencies and function relationships"""

    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)

    def analyze_file_dependencies(self, target_file: str) -> Dict:
        """Comprehensive dependency analysis for any C file"""
        return {
            'file_path': target_file,
            'functions': self._extract_functions(target_file),
            'includes': self._extract_includes(target_file),
            'called_functions': self._find_called_functions(target_file),
            'file_dependencies': self._find_file_dependencies(target_file)
        }

    def _extract_functions(self, file_path: str) -> List[Dict]:
        """Extract function signatures using regex parsing"""
        functions = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Remove comments and strings for cleaner parsing
            content_clean = re.sub(r'//.*?$|/\*.*?\*/|"(?:\\.|[^"\\])*"', '', content, flags=re.MULTILINE|re.DOTALL)

            # Match function definitions
            pattern = r'(\w+)\s+(\w+)\s*\([^)]*\)\s*\{'
            matches = re.finditer(pattern, content_clean)

            for match in matches:
                return_type, func_name = match.groups()
                functions.append({
                    'name': func_name,
                    'return_type': return_type,
                    'signature': f"{return_type} {func_name}(...)"
                })
        except Exception as e:
            print(f"Warning: Could not parse functions from {file_path}: {e}")

        return functions

    def _extract_includes(self, file_path: str) -> List[str]:
        """Extract all #include directives"""
        includes = []
        include_pattern = re.compile(r'^\s*#include\s+[<"]([^>"]+)[>"]', re.MULTILINE)

        try:
            with open(file_path, 'r') as f:
                content = f.read()
                includes = include_pattern.findall(content)
        except Exception:
            pass

        return includes

    def _find_called_functions(self, file_path: str) -> Set[str]:
        """Find all functions called from this file"""
        called_funcs = set()
        func_call_pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')

        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Remove comments, strings, and keywords
                content_clean = re.sub(r'//.*?$|/\*.*?\*/|"(?:\\.|[^"\\])*"', '', content, flags=re.MULTILINE|re.DOTALL)

                for match in func_call_pattern.finditer(content_clean):
                    func_name = match.group(1)
                    # Skip C keywords and common patterns
                    if func_name not in ['if', 'while', 'for', 'switch', 'return', 'sizeof', 'printf', 'malloc', 'free'] and not func_name[0].isupper():
                        called_funcs.add(func_name)
        except Exception:
            pass

        return called_funcs

    def _find_file_dependencies(self, file_path: str) -> List[str]:
        """Find other C files this file depends on"""
        dependencies = set()
        includes = self._extract_includes(file_path)

        for include in includes:
            if include.endswith('.h'):
                # Look for corresponding .c files
                base_name = include.replace('.h', '')
                possible_paths = [
                    os.path.join(os.path.dirname(file_path), f"{base_name}.c"),
                    os.path.join(self.repo_path, f"{base_name}.c"),
                    os.path.join(self.repo_path, "src", f"{base_name}.c"),
                    os.path.join(self.repo_path, "source", f"{base_name}.c"),
                    os.path.join(self.repo_path, "lib", f"{base_name}.c"),
                ]

                for possible_path in possible_paths:
                    if os.path.exists(possible_path):
                        dependencies.add(possible_path)
                        break

        return list(dependencies)

    def find_all_c_files(self) -> List[str]:
        """Find all C files in the repository, ONLY processing files under src/ directory"""
        c_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Only process files in the src directory
            if 'src' not in root.replace('\\', '/').split('/'):
                continue

            # Skip common build and hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and
                      d not in ['build', 'cmake-build', 'node_modules']]

            for file in files:
                if file.endswith('.c'):
                    file_path = os.path.join(root, file)

                    # Additional safety checks - skip any remaining test or unity files
                    file_lower = file.lower()
                    if (file_lower.startswith('test_') or
                        'unity' in file_lower or
                        'test' in file_lower):
                        continue

                    c_files.append(file_path)
        return c_files

    def find_function_implementations(self, function_names: List[str]) -> Dict[str, str]:
        """Find which files implement the given functions"""
        implementations = {}
        all_c_files = self.find_all_c_files()

        for func_name in function_names:
            for file_path in all_c_files:
                functions = self._extract_functions(file_path)
                for func in functions:
                    if func['name'] == func_name:
                        implementations[func_name] = file_path
                        break
                if func_name in implementations:
                    break

        return implementations