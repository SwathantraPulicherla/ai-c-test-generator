"""
Test Validator - Validates generated test files
"""

import os
import re
from typing import Dict, List

from .analyzer import DependencyAnalyzer


class TestValidator:
    """Universal C Test File Validator - Repo Independent"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.analyzer = DependencyAnalyzer(repo_path)

    def validate_test_file(self, test_file_path: str, source_file_path: str) -> Dict:
        """
        Validate a generated test file against its source file using comprehensive criteria
        """
        validation_result = {
            'file': os.path.basename(test_file_path),
            'compiles': True,
            'realistic': True,
            'quality': 'High',
            'issues': [],
            'keep': [],
            'fix': [],
            'remove': []
        }

        try:
            # Read both files
            with open(test_file_path, 'r') as f:
                test_content = f.read()
            with open(source_file_path, 'r') as f:
                source_content = f.read()

            # Extract source function signatures
            source_functions = self.analyzer._extract_functions(source_file_path)
            source_includes = self.analyzer._extract_includes(source_file_path)

            # 1. COMPILATION SAFETY CHECKS
            self._check_compilation_safety(test_content, source_functions, source_includes, validation_result)

            # 2. REALITY CHECKS
            self._check_reality_tests(test_content, source_functions, validation_result)

            # 3. TEST QUALITY ASSESSMENT
            self._assess_test_quality(test_content, source_functions, validation_result)

            # 4. LOGICAL CONSISTENCY VERIFICATION
            self._verify_logical_consistency(test_content, validation_result)

            # Determine overall quality rating
            validation_result['quality'] = self._calculate_quality_rating(validation_result)

        except Exception as e:
            validation_result['issues'].append(f"Validation error: {str(e)}")
            validation_result['compiles'] = False
            validation_result['quality'] = 'Low'

        return validation_result

    def _check_compilation_safety(self, test_content: str, source_functions: List[Dict], source_includes: List[str], result: Dict):
        """Check compilation safety criteria"""

        # Check for markdown markers (should be removed by post-processing)
        if '```' in test_content:
            result['issues'].append("Found markdown code block markers (```) - should be removed")
            result['compiles'] = False

        # Check for required includes
        required_includes = ['unity.h'] + [f"{func['name']}.h" for func in source_functions if func['name'] != 'main']
        for include in required_includes:
            if f'#include "{include}"' not in test_content and f'#include <{include}>' not in test_content:
                if include == 'unity.h':
                    result['issues'].append(f"Missing required Unity include: #include \"unity.h\"")
                    result['compiles'] = False

        # Check for invalid includes (headers that don't exist)
        invalid_includes = []
        include_pattern = re.compile(r'#include\s+["<]([^">]+)[">]')
        # Common standard C library headers that are acceptable in tests
        standard_headers = {'stdio.h', 'stdlib.h', 'string.h', 'math.h', 'assert.h', 'ctype.h', 'errno.h', 'limits.h', 'stdarg.h', 'stddef.h', 'stdint.h', 'stdbool.h', 'time.h'}
        
        for match in include_pattern.finditer(test_content):
            header = match.group(1)
            # Allow unity.h, standard library headers, and headers from source
            if header != 'unity.h' and header not in standard_headers and header not in source_includes:
                # Check if it's a valid header file that should exist
                if not any(header in inc for inc in source_includes):
                    invalid_includes.append(header)

        if invalid_includes:
            result['issues'].append(f"Invalid includes for non-existent headers: {invalid_includes}")
            result['compiles'] = False

        # Check function signature matches
        test_functions = self._extract_test_functions(test_content)
        for test_func in test_functions:
            if 'test_' in test_func['name']:
                # Check if stub functions match source signatures
                stub_matches = re.findall(r'(\w+)\s+(\w+)\s*\([^)]*\)\s*\{', test_content)
                for return_type, func_name in stub_matches:
                    # Find matching source function
                    source_match = next((f for f in source_functions if f['name'] == func_name), None)
                    if source_match and source_match['return_type'] != return_type:
                        result['issues'].append(f"Stub function {func_name} return type mismatch: {return_type} vs {source_match['return_type']}")
                        result['compiles'] = False

        # Check for duplicate symbols
        function_names = [f['name'] for f in test_functions]
        if len(function_names) != len(set(function_names)):
            duplicates = [name for name in function_names if function_names.count(name) > 1]
            result['issues'].append(f"Duplicate function definitions: {duplicates}")
            result['compiles'] = False

        # Check for invalid function calls (like main()) - but allow if main() is simple and testable
        # Only flag actual calls to main(), not the test runner's main() function definition
        main_calls = re.findall(r'\bmain\s*\([^)]*\)\s*;', test_content)
        if main_calls:
            # Allow main() testing if it's declared as extern and called like a regular function
            # This is acceptable for simple main functions that don't have complex setup
            if not re.search(r'extern\s+int\s+main\s*\(\s*void\s*\)\s*;', test_content):
                result['issues'].append("Invalid call to main() function - not suitable for unit testing")
                result['compiles'] = False

    def _check_reality_tests(self, test_content: str, source_functions: List[Dict], result: Dict):
        """Validate reality checks"""

        # Check for invalid floating point assertions
        if 'TEST_ASSERT_EQUAL_FLOAT' in test_content:
            result['issues'].append("TEST_ASSERT_EQUAL_FLOAT used - will fail due to precision. Use TEST_ASSERT_FLOAT_WITHIN instead")
            result['realistic'] = False

        # Check for impossible test values
        impossible_patterns = [
            (r'-?273\.15f?', 'Absolute zero temperature test - physically impossible'),
            (r'1e10+', 'Extremely large values that may cause overflow'),
            (r'NULL.*=.*[^=!].*NULL', 'Testing NULL assignments that may crash'),
        ]

        lines = test_content.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern, description in impossible_patterns:
                if re.search(pattern, line):
                    result['issues'].append(f"Line {i}: {description} - unrealistic test scenario")
                    result['realistic'] = False

        # Check floating point comparisons have tolerance - only for actual assertions
        float_assertions = re.findall(r'TEST_ASSERT_FLOAT_WITHIN\s*\([^)]+\)', test_content)
        float_equal_assertions = re.findall(r'TEST_ASSERT_EQUAL_FLOAT\s*\([^)]+\)', test_content)

        # Only flag if there are float equality assertions without tolerance
        if float_equal_assertions and not float_assertions:
            result['issues'].append("TEST_ASSERT_EQUAL_FLOAT used - will fail due to precision. Use TEST_ASSERT_FLOAT_WITHIN instead")
            result['realistic'] = False

        # Check stub return types match expected ranges
        if 'temperature' in test_content.lower() or 'celsius' in test_content.lower():
            # Temperature should be reasonable range for the specific sensor
            temp_values = re.findall(r'(\d+\.?\d*)f?', test_content)
            for val in temp_values:
                try:
                    temp = float(val)
                    # Context-aware validation: check if this looks like a raw ADC value or temperature
                    # Raw ADC values are typically 0-1023, temperatures are usually < 200°C
                    if temp > 200.0 and temp <= 1024.0:
                        # This might be a raw ADC value, not a temperature - check context
                        if 'raw' in test_content.lower() or 'adc' in test_content.lower() or '1023' in test_content:
                            continue  # Likely a raw ADC value, skip validation
                        else:
                            result['issues'].append(f"Temperature value {temp} seems unreasonably high")
                            result['realistic'] = False
                    elif temp > 1024.0:  # Definitely too high
                        result['issues'].append(f"Temperature value {temp} seems unreasonably high")
                        result['realistic'] = False
                    elif temp < -100.0:  # Definitely too low
                        result['issues'].append(f"Temperature value {temp} seems unreasonably low")
                        result['realistic'] = False
                except ValueError:
                    pass

    def _assess_test_quality(self, test_content: str, source_functions: List[Dict], result: Dict):
        """Assess test quality criteria"""

        test_functions = self._extract_test_functions(test_content)
        test_names = [f['name'] for f in test_functions if f['name'].startswith('test_')]

        # Check for edge cases
        edge_case_indicators = ['min', 'max', 'zero', 'negative', 'boundary', 'edge', 'limit']
        has_edge_cases = any(any(indicator in name.lower() for indicator in edge_case_indicators) for name in test_names)

        if not has_edge_cases and len(test_names) > 1:
            result['issues'].append("Missing edge case tests (min/max values, boundaries)")

        # Check for error conditions
        error_indicators = ['error', 'fail', 'invalid', 'null', 'boundary']
        has_error_tests = any(any(indicator in name.lower() for indicator in error_indicators) for name in test_names)

        # Check setUp/tearDown usage
        has_setup = 'setUp(' in test_content
        has_teardown = 'tearDown(' in test_content

        if has_setup and has_teardown:
            # Check if there are stub variables that need resetting
            # Stub variables typically start with 'g_' and are used for call counts/return values
            stub_variables = re.findall(r'static\s+\w+\s+g_\w+;', test_content)
            
            if stub_variables:  # Only require tearDown resets if there are actual stub variables
                # Verify stubs are reset - check for either reset functions or direct variable resets
                has_reset_functions = 'reset_' in test_content
                # Check for direct variable resets in tearDown (e.g., var_name = 0)
                teardown_section = re.search(r'void tearDown\(void\)\s*{([^}]*)}', test_content, re.DOTALL)
                has_direct_resets = False
                if teardown_section:
                    teardown_content = teardown_section.group(1)
                    # Look for variable assignments to 0, 0.0f, NULL, etc.
                    has_direct_resets = bool(re.search(r'\w+\s*=\s*(0|0\.0f|NULL|false|"DEFAULT");', teardown_content))

                if not has_reset_functions and not has_direct_resets:
                    result['issues'].append("tearDown() function should reset stub variables (call counts and return values)")

        # Check for meaningful test content
        if len(test_names) == 0:
            result['issues'].append("No test functions found (functions should start with 'test_')")

        # Check for test isolation (each test should be independent)
        if has_setup and has_teardown:
            # This is good - tests are properly isolated
            pass
        elif len(test_names) > 1:
            result['issues'].append("Multiple tests without setUp/tearDown - may not be properly isolated")

    def _verify_logical_consistency(self, test_content: str, result: Dict):
        """Verify logical consistency"""

        # Check for contradictory assertions in the same test
        test_sections = re.split(r'void test_\w+\s*\(', test_content)[1:]  # Split by test functions

        for i, section in enumerate(test_sections):
            test_name = f"test_{i+1}"  # Approximate name
            assertions = re.findall(r'TEST_ASSERT_\w+\s*\([^)]+\)', section)

            # Check for contradictory boolean assertions
            true_asserts = [a for a in assertions if 'TEST_ASSERT_TRUE' in a]
            false_asserts = [a for a in assertions if 'TEST_ASSERT_FALSE' in a]

            if true_asserts and false_asserts:
                # Check if they're testing different variables
                true_vars = [re.search(r'TEST_ASSERT_TRUE\s*\(\s*([^)]+)', a) for a in true_asserts]
                false_vars = [re.search(r'TEST_ASSERT_FALSE\s*\(\s*([^)]+)', a) for a in false_asserts]

                if true_vars and false_vars:
                    true_var_names = [match.group(1).strip() if match else "" for match in true_vars]
                    false_var_names = [match.group(1).strip() if match else "" for match in false_vars]

                    # If same variable has both TRUE and FALSE assertions, that's suspicious
                    common_vars = set(true_var_names) & set(false_var_names)
                    if common_vars:
                        result['issues'].append(f"Test {test_name}: contradictory assertions for variables {common_vars}")

        # Check for reasonable assertion values
        equal_assertions = re.findall(r'TEST_ASSERT_EQUAL\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', test_content)
        for expected, actual in equal_assertions:
            # Check for obviously wrong assertions like TEST_ASSERT_EQUAL(1, 2)
            try:
                exp_val = int(expected.strip())
                act_val = int(actual.strip())
                if exp_val != act_val and abs(exp_val - act_val) > 1000:  # Large difference
                    result['issues'].append(f"Unreasonable assertion: TEST_ASSERT_EQUAL({exp_val}, {act_val})")
            except (ValueError, AttributeError):
                pass  # Not simple integers, skip

    def _calculate_quality_rating(self, result: Dict) -> str:
        """Calculate overall quality rating"""
        issues = len(result['issues'])

        if issues == 0 and result['compiles'] and result['realistic']:
            return 'High'
        elif issues <= 2 and result['compiles']:
            return 'Medium'
        else:
            return 'Low'

    def _extract_test_functions(self, content: str) -> List[Dict]:
        """Extract test function definitions from test content"""
        functions = []
        # Match function definitions
        func_pattern = r'(\w+)\s+(\w+)\s*\([^)]*\)\s*{'
        matches = re.findall(func_pattern, content)

        for return_type, func_name in matches:
            functions.append({
                'name': func_name,
                'return_type': return_type
            })

        return functions

    def print_validation_report(self, report: Dict):
        """Print a formatted validation report"""
        print(f"\n📋 {report['file']}")
        print(f"   Quality: {report['quality']}")
        print(f"   Compiles: {'✅' if report['compiles'] else '❌'}")
        print(f"   Realistic: {'✅' if report['realistic'] else '❌'}")

        if report['issues']:
            print(f"   Issues ({len(report['issues'])}):")
            for issue in report['issues'][:5]:  # Show first 5 issues
                print(f"     - {issue}")
            if len(report['issues']) > 5:
                print(f"     ... and {len(report['issues']) - 5} more")

    def save_validation_report(self, report: Dict, report_dir: str):
        """Save validation report to file"""
        os.makedirs(report_dir, exist_ok=True)

        base_name = os.path.splitext(report['file'])[0]
        compiles_status = "compiles_yes" if report['compiles'] else "compiles_no"
        filename = f"{base_name}_{compiles_status}.txt"
        filepath = os.path.join(report_dir, filename)

        with open(filepath, 'w') as f:
            f.write(f"Validation Report for {report['file']}\n")
            f.write(f"Quality: {report['quality']}\n")
            f.write(f"Compiles: {report['compiles']}\n")
            f.write(f"Realistic: {report['realistic']}\n")
            f.write(f"Issues: {len(report['issues'])}\n")
            f.write("\nIssues:\n")
            for issue in report['issues']:
                f.write(f"- {issue}\n")

            if report['keep']:
                f.write("\nKeep:\n")
                for item in report['keep']:
                    f.write(f"- {item}\n")

            if report['fix']:
                f.write("\nFix:\n")
                for item in report['fix']:
                    f.write(f"- {item}\n")

            if report['remove']:
                f.write("\nRemove:\n")
                for item in report['remove']:
                    f.write(f"- {item}\n")