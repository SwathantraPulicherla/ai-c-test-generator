"""
AI Test Generator - Core test generation logic
"""

import os
import re
from pathlib import Path
from typing import Dict, List

import google.generativeai as genai

from .analyzer import DependencyAnalyzer


class SmartTestGenerator:
    """AI-powered test generator using Google Gemini"""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        # Try new API first (v0.8+), fall back to old API
        try:
            # Try different model names for new API
            for model_name in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    self.use_new_api = True
                    print(f"✅ Using model: {model_name}")
                    break
                except Exception as e:
                    print(f"⚠️  Model {model_name} failed: {e}")
                    continue
            else:
                raise Exception("No compatible model found")
        except (AttributeError, Exception):
            # Fall back to older API (v0.1.0rc1)
            self.model = None
            self.use_new_api = False
            print("📋 Using legacy API (v0.1.0rc1)")
        self.dependency_map = {}

    def build_dependency_map(self, repo_path: str) -> Dict[str, str]:
        """Build a map of function_name -> source_file for the entire repository"""
        print("📋 Building global dependency map...")
        analyzer = DependencyAnalyzer(repo_path)
        all_c_files = analyzer.find_all_c_files()

        dependency_map = {}

        for file_path in all_c_files:
            functions = analyzer._extract_functions(file_path)
            for func in functions:
                dependency_map[func['name']] = file_path

        print(f"   Mapped {len(dependency_map)} functions across {len(all_c_files)} files")
        return dependency_map

    def generate_tests_for_file(self, file_path: str, repo_path: str, output_dir: str, dependency_map: Dict[str, str]) -> Dict:
        """Generate tests for a SINGLE file with proper context"""
        analyzer = DependencyAnalyzer(repo_path)

        # Analyze this specific file
        analysis = analyzer.analyze_file_dependencies(file_path)

        # IDENTIFY FUNCTIONS THAT NEED STUBS
        functions_that_need_stubs = []
        implemented_functions = {f['name'] for f in analysis['functions']}

        for called_func in analysis['called_functions']:
            # If called function is not in current file AND not a standard library function
            if (called_func not in implemented_functions and
                called_func in dependency_map and
                dependency_map[called_func] != file_path):
                functions_that_need_stubs.append(called_func)

        print(f"   📋 {os.path.basename(file_path)}: {len(analysis['functions'])} functions, {len(functions_that_need_stubs)} need stubs")

        # Build targeted prompt for this file only
        prompt = self._build_targeted_prompt(analysis, functions_that_need_stubs, repo_path)

        # Generate tests
        try:
            if self.use_new_api:
                response = self.model.generate_content(prompt)
                test_code = response.text.strip()
            else:
                # Use older API (v0.1.0rc1) - try different approaches
                try:
                    # Try with model specification
                    model = genai.GenerativeModel('gemini-pro')
                    response = model.generate_content(prompt)
                    test_code = response.text.strip()
                except:
                    # Fall back to direct generate_text if available
                    try:
                        response = genai.generate_text(prompt=prompt)
                        test_code = response.result.strip()
                    except:
                        # Last resort - try basic completion
                        response = genai.generate_text(model='gemini-pro', prompt=prompt)
                        test_code = response.result.strip()

            # POST-PROCESSING: Clean up common AI generation issues
            test_code = self._post_process_test_code(test_code, analysis, analysis['includes'])

            # Save test file
            test_filename = f"test_{os.path.basename(file_path)}"
            output_path = os.path.join(output_dir, test_filename)

            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(test_code)

            return {'success': True, 'test_file': output_path}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _build_targeted_prompt(self, analysis: Dict, functions_that_need_stubs: List[str], repo_path: str) -> str:
        """Build a focused prompt for a single file with stub requirements"""

        file_content = self._read_file_safely(analysis['file_path'])
        rel_path = os.path.relpath(analysis['file_path'], repo_path)

        prompt = f"""
Generate Unity tests for this C file: {rel_path}

SOURCE CODE TO TEST:
```c
{file_content}
```

FUNCTIONS TO TEST:
{chr(10).join(f"- {func['return_type']} {func['name']}" for func in analysis['functions'])}

FUNCTIONS THAT NEED STUBS (implement these as stub functions):
{chr(10).join(f"- {func_name}" for func_name in functions_that_need_stubs) or "- None"}

CRITICAL REQUIREMENTS - FOLLOW THESE EXACTLY TO AVOID COMPILATION ERRORS:

1. OUTPUT FORMAT:
   - Generate ONLY clean C code with NO markdown markers (```c, ```)
   - NO explanations, comments about generation, or extra text
   - Start directly with #include statements

2. COMPILATION SAFETY:
   - Include ONLY "unity.h" and existing header files from the source
   - DO NOT include non-existent headers (like "main.h" if no main.h exists)
   - Function signatures must EXACTLY match the source code
   - NO calls to main() or other functions that don't exist in testable form

3. FLOATING POINT HANDLING:
   - ALWAYS use TEST_ASSERT_FLOAT_WITHIN(tolerance, expected, actual)
   - NEVER use TEST_ASSERT_EQUAL_FLOAT (causes precision failures)
   - Use tolerance 0.01f for temperature comparisons

4. STUB IMPLEMENTATION:
   - Implement stubs for ALL listed functions that need stubs
   - Stubs must have EXACT same signature as source functions
   - Use static variables for call counts and return values
   - Reset ALL stub state in setUp() function

5. TEST DESIGN:
   - Test functions individually, not main() or complex workflows
   - Use realistic values within sensor operational ranges
   - Include setUp() and tearDown() for proper isolation
   - Each test should be independent and focused

6. UNITY FRAMEWORK USAGE:
   - Use TEST_ASSERT_* macros correctly
   - TEST_ASSERT_TRUE/TEST_ASSERT_FALSE for boolean results
   - TEST_ASSERT_EQUAL for integers
   - TEST_ASSERT_FLOAT_WITHIN for floating point
   - TEST_ASSERT_EQUAL_STRING for string comparisons

VALIDATION REQUIREMENTS - FOLLOW THESE CRITERIA:

1. COMPILATION SAFETY:
   - Include ALL necessary headers (#include "unity.h", source headers)
   - Ensure stub function signatures EXACTLY match source function signatures
   - No duplicate symbol definitions

2. REALITY CHECKS:
   - Use realistic test values within operational ranges
   - Avoid impossible scenarios (temperatures below absolute zero, etc.)
   - Stubs must match actual function return types and parameters
   - Use appropriate tolerance for floating-point comparisons (TEST_ASSERT_FLOAT_WITHIN)

3. TEST QUALITY:
   - Cover edge cases (min/max values, zero, boundaries)
   - Test error conditions where applicable
   - Reset stubs properly in setUp()/tearDown() functions
   - Each test should verify meaningful behavior
   - Avoid redundant or trivial test cases

4. LOGICAL CONSISTENCY:
   - Test names should match their actual content
   - No contradictory assertions within tests
   - Use reasonable threshold values for comparisons
   - Proper use of TEST_ASSERT_* macros
   - tearDown() must reset ALL stub variables (call counts and return values) to 0/default values

INSTRUCTIONS:

Create a complete Unity test file named test_{os.path.basename(analysis['file_path'])}

Generate stub functions for ALL listed functions that need stubs
Stubs should track call counts and allow configuring return values

Test normal cases, edge cases, and error conditions
Use TEST_ASSERT_* macros appropriately
Include setUp() and tearDown() functions for proper test isolation
CRITICAL: tearDown() must reset ALL stub variables (call counts and return values) to 0/default values

Generate ONLY the complete C test file code. No explanations.
"""
        return prompt

    def _read_file_safely(self, file_path: str) -> str:
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except Exception:
            return "// Unable to read file"

    def _post_process_test_code(self, test_code: str, analysis: Dict, source_includes: List[str]) -> str:
        """Post-process generated test code to fix common issues"""

        # Remove markdown code block markers
        test_code = re.sub(r'^```c?\s*', '', test_code, flags=re.MULTILINE)
        test_code = re.sub(r'```\s*$', '', test_code, flags=re.MULTILINE)

        # Fix floating point assertions - replace TEST_ASSERT_EQUAL_FLOAT with TEST_ASSERT_FLOAT_WITHIN
        test_code = re.sub(
            r'TEST_ASSERT_EQUAL_FLOAT\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)',
            r'TEST_ASSERT_FLOAT_WITHIN(0.01f, \1, \2)',
            test_code
        )

        # Remove invalid function calls (like main())
        test_code = re.sub(r'\bmain\s*\(\s*\)\s*;', '', test_code)
        # Remove any main function definitions that might appear
        test_code = re.sub(r'int\s+main\s*\([^)]*\)\s*{[^}]*}', '', test_code, flags=re.DOTALL)

        # Remove printf/scanf statements that might appear in tests
        test_code = re.sub(r'printf\s*\([^;]*\);\s*', '', test_code)
        test_code = re.sub(r'scanf\s*\([^;]*\);\s*', '', test_code)

        # Ensure proper includes - only include unity.h and existing source headers
        lines = test_code.split('\n')
        cleaned_lines = []

        for line in lines:
            # Keep unity.h include
            if '#include "unity.h"' in line:
                cleaned_lines.append(line)
                continue

            # Only keep includes for headers that exist in source_includes or are standard headers
            if line.startswith('#include'):
                include_match = re.match(r'#include\s+["<]([^">]+)[">]', line)
                if include_match:
                    header_name = include_match.group(1)
                    # Only include headers that exist in source_includes or are standard headers
                    if header_name in source_includes or header_name.endswith('.h'):
                        # Additional check: don't include main.h if it doesn't exist
                        if header_name == 'main.h' and not any('main.h' in inc for inc in source_includes):
                            continue
                        cleaned_lines.append(line)
                # Skip non-matching include lines
                continue

            # Keep all other lines
            cleaned_lines.append(line)

        # Ensure unity.h is included if not present
        has_unity = any('#include "unity.h"' in line for line in cleaned_lines)
        if not has_unity:
            cleaned_lines.insert(0, '#include "unity.h"')

        # Add Unity main function with RUN_TEST calls for all test functions
        test_code_with_main = '\n'.join(cleaned_lines)
        test_functions = re.findall(r'void\s+(test_\w+)\s*\(', test_code_with_main)

        if test_functions:
            main_function = '\n\nint main(void) {\n    UNITY_BEGIN();\n\n'
            for test_func in test_functions:
                main_function += f'    RUN_TEST({test_func});\n'
            main_function += '\n    return UNITY_END();\n}'

            test_code_with_main += main_function

        return test_code_with_main