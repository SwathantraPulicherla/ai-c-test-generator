"""
Code Navigator - Interactive C code navigation and exploration
"""

import os
import re
from typing import List, Dict, Set, Optional
from pathlib import Path

from .analyzer import DependencyAnalyzer


class CodeNavigator:
    """Interactive code navigation tool for C projects"""

    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.analyzer = DependencyAnalyzer(repo_path)
        self.function_cache: Dict[str, Dict] = {}
        self.file_cache: Dict[str, List[Dict]] = {}

    def find_function_definition(self, function_name: str) -> Optional[Dict]:
        """Find where a function is defined"""
        print(f"🔍 Searching for function definition: {function_name}")

        # Check cache first
        if function_name in self.function_cache:
            return self.function_cache[function_name]

        # Search all C files in the repository (not just src/)
        all_files = self._find_all_c_files()

        for file_path in all_files:
            functions = self.analyzer._extract_functions(file_path)
            for func in functions:
                if func['name'] == function_name:
                    result = {
                        'name': func['name'],
                        'file': file_path,
                        'line': 'unknown',  # analyzer doesn't provide line numbers
                        'signature': func['signature']
                    }
                    self.function_cache[function_name] = result
                    return result

        return None

    def find_function_calls(self, function_name: str) -> List[Dict]:
        """Find all places where a function is called"""
        print(f"🔍 Finding all calls to: {function_name}")

        calls = []
        all_files = self._find_all_c_files()

        for file_path in all_files:
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    # Simple regex to find function calls
                    if re.search(rf'\b{re.escape(function_name)}\s*\(', line):
                        # Skip if it's a function definition
                        if re.search(rf'\w+\s+{re.escape(function_name)}\s*\(', line):
                            continue

                        calls.append({
                            'file': file_path,
                            'line': line_num,
                            'context': line.strip()
                        })
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")

        return calls

    def get_file_functions(self, file_path: str) -> List[Dict]:
        """Get all functions defined in a file"""
        if file_path in self.file_cache:
            return self.file_cache[file_path]

        functions = self._get_functions_from_file(file_path)
        self.file_cache[file_path] = functions
        return functions

    def _find_all_c_files(self) -> List[str]:
        """Find all C files in the repository (navigation version - more permissive)"""
        c_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip common build and hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and
                      d not in ['node_modules', 'cmake-build', 'build', 'dist', 'venv', '.venv']]

            for file in files:
                if file.endswith('.c'):
                    file_path = os.path.join(root, file)
                    c_files.append(file_path)
        return c_files
        """Extract functions with line numbers"""
        functions = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')

            # Remove comments and strings for cleaner parsing
            content_clean = re.sub(r'//.*?$|/\*.*?\*/|"(?:\\.|[^"\\])*"', '', content, flags=re.MULTILINE|re.DOTALL)

            # Match function definitions with line numbers
            pattern = r'(\w+)\s+(\w+)\s*\([^)]*\)\s*\{'
            matches = re.finditer(pattern, content_clean)

            for match in matches:
                return_type, func_name = match.groups()

                # Find the line number
                line_num = content[:match.start()].count('\n') + 1

                functions.append({
                    'name': func_name,
                    'return_type': return_type,
                    'signature': f"{return_type} {func_name}(...)",
                    'line': line_num
                })

        except Exception as e:
            print(f"Warning: Could not parse functions from {file_path}: {e}")

        return functions

    def show_function_info(self, function_name: str):
        """Display comprehensive information about a function"""
        print(f"\n{'='*60}")
        print(f"FUNCTION: {function_name}")
        print('='*60)

        # Find definition
        definition = self.find_function_definition(function_name)
        if definition:
            print("📍 DEFINITION:")
            print(f"   File: {os.path.relpath(definition['file'], self.repo_path)}")
            print(f"   Line: {definition['line']}")
            print(f"   Signature: {definition['signature']}")
        else:
            print("❌ Definition not found")
            return

        # Find calls
        calls = self.find_function_calls(function_name)
        if calls:
            print(f"\n📞 CALLED FROM ({len(calls)} locations):")
            for call in calls[:10]:  # Show first 10 calls
                rel_path = os.path.relpath(call['file'], self.repo_path)
                print(f"   {rel_path}:{call['line']} - {call['context'][:60]}...")
            if len(calls) > 10:
                print(f"   ... and {len(calls) - 10} more locations")
        else:
            print("\n📞 No calls found")

        print()

    def interactive_navigate(self):
        """Interactive navigation mode"""
        print("🎯 C Code Navigator - Interactive Mode")
        print("Commands:")
        print("  'func <name>' - Show function information")
        print("  'calls <name>' - Show where function is called")
        print("  'file <path>' - Show functions in file")
        print("  'quit' or 'q' - Exit")
        print()

        while True:
            try:
                cmd = input("navigate> ").strip()

                if not cmd:
                    continue

                if cmd.lower() in ['quit', 'q', 'exit']:
                    break

                parts = cmd.split()
                command = parts[0].lower()

                if command == 'func' and len(parts) > 1:
                    func_name = parts[1]
                    self.show_function_info(func_name)

                elif command == 'calls' and len(parts) > 1:
                    func_name = parts[1]
                    calls = self.find_function_calls(func_name)
                    if calls:
                        print(f"\n📞 {func_name} is called from:")
                        for call in calls:
                            rel_path = os.path.relpath(call['file'], self.repo_path)
                            print(f"  {rel_path}:{call['line']}")
                    else:
                        print(f"❌ No calls to {func_name} found")

                elif command == 'file' and len(parts) > 1:
                    file_path = parts[1]
                    if not os.path.isabs(file_path):
                        file_path = os.path.join(self.repo_path, file_path)

                    if os.path.exists(file_path):
                        functions = self.get_file_functions(file_path)
                        rel_path = os.path.relpath(file_path, self.repo_path)
                        print(f"\n📁 {rel_path} - {len(functions)} functions:")
                        for func in functions:
                            print(f"  {func['signature']} (line {func['line']})")
                    else:
                        print(f"❌ File not found: {file_path}")

                else:
                    print("❌ Unknown command. Use 'func', 'calls', 'file', or 'quit'")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")