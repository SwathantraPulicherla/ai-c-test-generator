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

        # Use modern API (v0.8.0+) with fallback models
        self.models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
        self.model = None

        for model_name in self.models_to_try:
            try:
                self.model = genai.GenerativeModel(model_name)
                print(f"✅ Using model: {model_name}")
                break
            except Exception as e:
                print(f"⚠️  Model {model_name} failed: {e}")
                continue

        if self.model is None:
            raise Exception("No compatible Gemini model found. Please check your API key and internet connection.")

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

        # Generate tests using modern API
        try:
            response = self.model.generate_content(prompt)
            test_code = response.text.strip()

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
Generate HIGH-QUALITY Unity tests for this C file: {rel_path}

SOURCE CODE TO TEST:
```c
{file_content}
```

FUNCTIONS TO TEST:
{chr(10).join(f"- {func['return_type']} {func['name']}" for func in analysis['functions'])}

FUNCTIONS THAT NEED STUBS (implement these as configurable stub functions):
{chr(10).join(f"- {func_name}" for func_name in functions_that_need_stubs) or "- None"}

# CRITICAL REQUIREMENTS FOR HIGH-QUALITY TESTS

## 1. OUTPUT FORMAT:
   - Generate ONLY clean C code with NO markdown markers (```c, ```)
   - NO explanations, comments about generation, or extra text
   - Start directly with #include statements

## 2. COMPILATION SAFETY:
   - Include ONLY "unity.h" and existing header files from the source
   - DO NOT include non-existent headers
   - Function signatures must EXACTLY match the source code
   - NO calls to main() or functions that don't exist

## 3. REALISTIC TEST VALUES (CRITICAL FOR QUALITY):
   - Temperature sensors: -40°C to +125°C (normal range: 0°C to 50°C)
   - Voltage sensors: 0V to 5V (never negative or >5.5V)
   - Current sensors: 0A to 10A (never negative)
   - Counters/timers: 0 to UINT32_MAX
   - Boolean states: only 0 or 1, true or false
   - NEVER test impossible values like absolute zero (-273°C) or negative voltages

## 4. FLOATING POINT HANDLING:
   - ALWAYS use TEST_ASSERT_FLOAT_WITHIN(tolerance, expected, actual)
   - Temperature tolerance: 0.1f degrees
   - Voltage tolerance: 0.01f volts
   - Current tolerance: 0.001f amps
   - NEVER use TEST_ASSERT_EQUAL_FLOAT

## 5. STUB IMPLEMENTATION (HIGH QUALITY):
   - Implement stubs for ALL listed functions that need stubs
   - Stubs must have EXACT same signature as source functions
   - Use static variables: call_count, return_value, last_param
   - setUp(): Reset ALL stub variables to 0/default
   - tearDown(): Reset ALL stub variables to 0/default
   - Allow test code to configure stub return values

## 6. COMPREHENSIVE TEST SCENARIOS:

### NORMAL OPERATION TESTS:
   - Test with typical values in middle of operational range
   - Test expected behavior under normal conditions
   - Verify correct calculations and logic

### EDGE CASE TESTS:
   - Minimum operational values (e.g., 0°C for temperature)
   - Maximum operational values (e.g., 125°C for temperature)
   - Boundary conditions (just above/below limits)
   - Zero values where applicable
   - Maximum valid values

### ERROR CONDITION TESTS:
   - Invalid inputs (out of range values)
   - NULL pointers (if applicable)
   - Division by zero scenarios
   - Overflow conditions

## 7. UNITY FRAMEWORK BEST PRACTICES:
   - TEST_ASSERT_TRUE/TEST_ASSERT_FALSE for boolean results
   - TEST_ASSERT_EQUAL for integers and enums
   - TEST_ASSERT_FLOAT_WITHIN for floating point
   - TEST_ASSERT_EQUAL_STRING for strings
   - TEST_ASSERT_NULL/TEST_ASSERT_NOT_NULL for pointers

## 8. TEST ISOLATION & STRUCTURE:
   - Each test function tests ONE specific behavior
   - Use descriptive test names: test_[function]_[scenario]
   - setUp() initializes test state
   - tearDown() cleans up and resets stubs
   - Tests should be independent and repeatable

# QUALITY VALIDATION CRITERIA (YOU MUST MEET THESE):

✅ COMPILATION: Code must compile without errors
✅ REALISTIC: Use only physically possible test values
✅ EDGE CASES: Include min/max/boundary value tests
✅ STUB RESET: tearDown() must reset ALL stub variables
✅ FLOAT TOLERANCE: Use TEST_ASSERT_FLOAT_WITHIN, never TEST_ASSERT_EQUAL_FLOAT
✅ TEST ISOLATION: Each test independent, proper setUp/tearDown
✅ MEANINGFUL ASSERTIONS: Test actual behavior, not just function calls

# INSTRUCTIONS:

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
        """Post-process generated test code to fix common issues and improve quality"""

        # Remove markdown code block markers
        test_code = re.sub(r'^```c?\s*', '', test_code, flags=re.MULTILINE)
        test_code = re.sub(r'```\s*$', '', test_code, flags=re.MULTILINE)

        # Fix floating point assertions - replace TEST_ASSERT_EQUAL_FLOAT with TEST_ASSERT_FLOAT_WITHIN
        test_code = re.sub(
            r'TEST_ASSERT_EQUAL_FLOAT\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)',
            r'TEST_ASSERT_FLOAT_WITHIN(0.01f, \1, \2)',
            test_code
        )

        # Fix unrealistic temperature values (absolute zero or impossible ranges)
        test_code = re.sub(r'-273\.15f?', '-40.0f', test_code)  # Replace absolute zero with realistic minimum
        test_code = re.sub(r'1e10+', '1000.0f', test_code)      # Replace extremely large values

        # Fix negative voltage/current values (replace with 0)
        test_code = re.sub(r'-\d+\.?\d*f?\b', '0.0f', test_code)

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