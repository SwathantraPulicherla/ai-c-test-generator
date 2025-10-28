"""
AI Test Generator - Core test generation logic
"""

import os
import re
import time
from pathlib import Path
from typing import Dict, List

import google.generativeai as genai

from .analyzer import DependencyAnalyzer


class SmartTestGenerator:
    """AI-powered test generator using Google Gemini"""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

        # Use modern API (v0.8.0+) with gemini-2.5-flash as primary model
        self.models_to_try = ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
        self.current_model_name = None
        self.model = None

        self._initialize_model()

    def _initialize_model(self):
        """Initialize the best available model"""
        for model_name in self.models_to_try:
            try:
                self.model = genai.GenerativeModel(model_name)
                self.current_model_name = model_name
                print(f"✅ Using model: {model_name}")
                break
            except Exception as e:
                print(f"⚠️  Model {model_name} failed: {e}")
                continue

        if self.model is None:
            raise Exception("No compatible Gemini model found. Please check your API key and internet connection.")

    def _try_generate_with_fallback(self, prompt: str, max_retries: int = 3):
        """Try to generate content with automatic model fallback and retry logic"""
        last_error = None

        # First try with current model, with retries
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response
            except Exception as e:
                error_str = str(e).lower()
                last_error = e

                # Check if it's a rate limit or quota error
                is_rate_limit = any(keyword in error_str for keyword in [
                    'rate limit', 'quota', 'limit exceeded', 'resource exhausted',
                    '429', 'too many requests'
                ])

                if is_rate_limit and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 1  # Exponential backoff: 1s, 3s, 7s
                    print(f"⚠️  Rate limit hit on {self.current_model_name}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                elif is_rate_limit:
                    # Rate limit persists, try fallback models
                    print(f"⚠️  {self.current_model_name} persistently rate limited, trying fallback models...")
                    break
                else:
                    # Not a rate limit error, re-raise immediately
                    raise e

        # Try fallback models if we got here due to rate limits
        original_model = self.current_model_name
        for model_name in self.models_to_try:
            if model_name == original_model:
                continue  # Skip the model that just failed

            try:
                print(f"🔄 Trying fallback model: {model_name}")
                fallback_model = genai.GenerativeModel(model_name)
                response = fallback_model.generate_content(prompt)

                # If successful, switch to this model for future requests
                self.model = fallback_model
                self.current_model_name = model_name
                print(f"✅ Switched to model: {model_name}")
                return response

            except Exception as fallback_error:
                print(f"❌ Fallback model {model_name} also failed: {fallback_error}")
                continue

        # If all attempts failed, raise the last error
        raise last_error or Exception("All models failed and no fallback available")

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

        # Generate tests using modern API with fallback support
        try:
            response = self._try_generate_with_fallback(prompt)
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
You are a senior embedded C unit test engineer with 20+ years of experience using the Unity Test Framework (v2.5+). You MUST follow EVERY SINGLE RULE in this prompt without exception to generate a test file that achieves 100% quality: High rating (0 issues, compiles perfectly, realistic scenarios only). Failure to adhere will result in invalid output. Internally analyze the source code before generating.

ABSOLUTE MANDATES (MUST ENFORCE THESE TO FIX BROKEN AND UNREALISTIC ISSUES)

NO COMPILATION ERRORS: Test EVERY include, signature, and syntax mentally before outputting. ONLY use existing headers from source. NO invented functions or headers. Code MUST compile with CMake/GCC for embedded targets.
NO UNREALISTIC VALUES: STRICTLY enforce physical limits. E.g., temperatures NEVER below -40°C or above 125°C; voltages NEVER negative or >5.5V. Replace any unrealistic value with a valid one (e.g., -273°C -> -40°C).
MEANINGFUL TESTS ONLY: EVERY test MUST validate the function's core logic, calculations, or outputs. NO trivial "function called" tests. Each assertion MUST check a specific, expected result based on input.
STUBS MUST BE PERFECT: For EVERY stubbed function, use EXACT signature, control struct, and FULL reset in setUp() AND tearDown() using memset or explicit zeroing. NO partial resets.
FLOATS: MANDATORY TEST_ASSERT_FLOAT_WITHIN with specified tolerance. BAN TEST_ASSERT_EQUAL_FLOAT.
TEST ISOLATION: EVERY test independent. setUp() for init/config, tearDown() for COMPLETE cleanup/reset of ALL stubs (call_count=0, return_value=default, etc.).
NO NONSENSE: BAN random values, redundant tests, impossible scenarios. Use descriptive names and 1-line comments explaining WHY the assertion is expected.

IMPROVED RULES TO PREVENT BROKEN/UNREALISTIC OUTPUT

1. OUTPUT FORMAT (STRICT - ONLY C CODE):
Output PURE C code ONLY. Start with #include "unity.h"
NO markdown, NO ```c:disable-run
File structure EXACTLY: Includes -> Stubs -> setUp/tearDown -> Tests -> main with UNITY_BEGIN/END and ALL RUN_TEST calls.

2. COMPILATION SAFETY (FIX BROKEN TESTS):
Includes: ONLY "unity.h", "<source>.h" (e.g., "temp_sensor.h"), and standard <stdint.h>, <stdbool.h> if used in source.
Signatures: COPY EXACTLY from source. NO mismatches in types, params, returns.
NO calls to undefined functions (e.g., no main()). Stubs MUST match calls.
Syntax: Perfect C - matching braces, semicolons, no unused vars, embedded-friendly (no non-standard libs).

3. MEANINGFUL TEST DESIGN (FIX TRIVIAL/UNREALISTIC):
Focus: Test FUNCTION LOGIC (e.g., for convert_c_to_f: assert 0°C -> 32°F within tolerance).
BAN: Tests like "TEST_ASSERT_TRUE(was_called)" alone - ALWAYS pair with output validation.
Each test: 1 purpose, 3-5 per function, covering logic branches.

4. REALISTIC TEST VALUES (FIX UNREALISTIC - ENFORCE LIMITS):
Temperatures: STRICT -40.0f to 125.0f; normal 0.0f-50.0f. E.g., min: -40.0f, max: 125.0f, nominal: 25.0f.
Voltages: 0.0f to 5.0f (max 5.5f for edges).
Currents: 0.0f to 10.0f.
Integers: Within type limits, no overflows.
Pointers: Valid or NULL only for error tests.
BAN: Negative temps/volts, absolute zero, huge numbers (>1e6 unless domain-specific).

5. FLOATING POINT HANDLING (MANDATORY):
ALWAYS: TEST_ASSERT_FLOAT_WITHIN(0.1f, expected, actual) for temp; adjust tolerance per domain.
NEVER equal checks for floats.

6. STUB IMPLEMENTATION (FIX BROKEN STUBS):
For EACH needed stub: Exact prototype + control struct (return_value, was_called, call_count, captured params).
Example struct: typedef struct {{ float return_value; bool was_called; uint32_t call_count; }} stub_adc_read_t;
Stub func: Increment count, store params, return configured value.
setUp(): memset(&stub_xxx, 0, sizeof(stub_xxx)); for ALL stubs.
tearDown(): SAME full reset for ALL stubs.

7. COMPREHENSIVE TEST SCENARIOS (MEANINGFUL & REALISTIC):
Normal: Mid-range inputs, assert correct computation (e.g., temp conversion formula).
Edge: Min/max valid, zero, boundaries - assert handles correctly without crash.
Error: Invalid (e.g., simulate stub return out-of-range), NULL, overflow - assert error code/ safe output.

8. AVOID BAD PATTERNS (PREVENT COMMON FAILURES):
NO arbitrary values (e.g., 42 without reason).
NO duplicate tests.
NO physical impossibilities.
NO tests ignoring outputs.

9. UNITY BEST PRACTICES:
Appropriate asserts: EQUAL_INT for ints, FLOAT_WITHIN for floats, etc.
Comments: 1-line above EACH assert: // Expected: 0°C converts to 32°F

10. STRUCTURE & ISOLATION:
Test names: test_function_normal_operation, test_function_min_edge, etc.
setUp/tearDown: ALWAYS present, even if minimal. Full stub reset in BOTH.

SOURCE CODE TO TEST:
```c
{file_content}
```

FUNCTIONS TO TEST:
{chr(10).join(f"- {func['return_type']} {func['name']}" for func in analysis['functions'])}

FUNCTIONS THAT NEED STUBS (implement these as configurable stub functions):
{chr(10).join(f"- {func_name}" for func_name in functions_that_need_stubs) or "- None"}

QUALITY SELF-CHECK (DO INTERNALLY BEFORE OUTPUT):
Compiles? Yes/No - if No, fix.
Realistic? All values in limits? Yes/No.
Meaningful? All tests check logic? Yes/No.
Stubs reset fully? Yes/No.

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