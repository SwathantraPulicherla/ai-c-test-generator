#!/usr/bin/env python3
"""
CLI interface for AI C Test Generator
"""

import argparse
import os
import sys
from pathlib import Path

# Add compatibility for older Python versions
try:
    from importlib.metadata import packages_distributions
except ImportError:
    # Python < 3.10 compatibility
    try:
        from importlib_metadata import packages_distributions
    except ImportError:
        # Fallback implementation
        def packages_distributions():
            return {}

from .generator import SmartTestGenerator
from .validator import TestValidator
from .navigator import CodeNavigator


def create_parser():
    """Create argument parser for the CLI tool"""
    parser = argparse.ArgumentParser(
        description="AI-powered C unit test generator and code navigator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate tests for all C files in current directory
  ai-c-testgen --api-key YOUR_API_KEY

  # Generate tests for specific directory
  ai-c-testgen --repo-path /path/to/c/project --api-key YOUR_API_KEY

  # Navigate code interactively
  ai-c-testgen navigate --repo-path /path/to/c/project

  # Find function definition
  ai-c-testgen find-func my_function --repo-path /path/to/c/project

  # Find where function is called
  ai-c-testgen find-calls my_function --repo-path /path/to/c/project
        """
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=False)

    # Test generation command (default behavior)
    generate_parser = subparsers.add_parser('generate', help='Generate unit tests (default)')
    generate_parser.add_argument(
        '--repo-path',
        type=str,
        default='.',
        help='Path to the C repository (default: current directory)'
    )
    generate_parser.add_argument(
        '--output',
        type=str,
        default='tests',
        help='Output directory for generated tests (default: tests)'
    )
    generate_parser.add_argument(
        '--api-key',
        type=str,
        help='Google Gemini API key (can also use GEMINI_API_KEY env var)'
    )
    generate_parser.add_argument(
        '--source-dir',
        type=str,
        default='src',
        help='Source directory containing C files (default: src)'
    )
    generate_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    # Navigation commands
    navigate_parser = subparsers.add_parser('navigate', help='Interactive code navigation')
    navigate_parser.add_argument(
        '--repo-path',
        type=str,
        default='.',
        help='Path to the C repository (default: current directory)'
    )

    find_func_parser = subparsers.add_parser('find-func', help='Find function definition')
    find_func_parser.add_argument('function', help='Function name to find')
    find_func_parser.add_argument(
        '--repo-path',
        type=str,
        default='.',
        help='Path to the C repository (default: current directory)'
    )

    find_calls_parser = subparsers.add_parser('find-calls', help='Find where function is called')
    find_calls_parser.add_argument('function', help='Function name to search for')
    find_calls_parser.add_argument(
        '--repo-path',
        type=str,
        default='.',
        help='Path to the C repository (default: current directory)'
    )

    # Version
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )

    return parser


def handle_generate(args):
    """Handle test generation command"""
    if not validate_environment(args):
        return 1

    api_key = args.api_key or os.getenv('GEMINI_API_KEY')

    print("🚀 AI C Test Generator")
    print(f"   Repository: {args.repo_path}")
    print(f"   Source dir: {args.source_dir}")
    print(f"   Output dir: {args.output}")
    print()

    try:
        # Initialize components
        generator = SmartTestGenerator(api_key)
        validator = TestValidator(args.repo_path)

        # Build dependency map
        if args.verbose:
            print("📋 Building dependency map...")
        dependency_map = generator.build_dependency_map(args.repo_path)

        # Find C files in source directory
        source_path = os.path.join(args.repo_path, args.source_dir)
        c_files = []
        for root, dirs, files in os.walk(source_path):
            for file in files:
                if file.endswith('.c'):  # Only process .c files, not headers
                    c_files.append(os.path.join(root, file))

        if args.verbose:
            print(f"📁 Found {len(c_files)} C files to process")

        # Create output directory
        output_dir = os.path.join(args.repo_path, args.output)
        os.makedirs(output_dir, exist_ok=True)

        # Process each file
        successful_generations = 0
        validation_reports = []

        for file_path in c_files:
            rel_path = os.path.relpath(file_path, args.repo_path)
            print(f"🎯 Processing: {rel_path}")

            try:
                result = generator.generate_tests_for_file(
                    file_path, args.repo_path, output_dir, dependency_map
                )

                if result['success']:
                    print(f"   ✅ Generated: {os.path.basename(result['test_file'])}")
                    successful_generations += 1

                    # Validate the generated test
                    if args.verbose:
                        print(f"   🔍 Validating...")
                    validation_result = validator.validate_test_file(result['test_file'], file_path)
                    validation_reports.append(validation_result)

                    # Print validation summary
                    status = "✅" if validation_result['compiles'] and validation_result['realistic'] else "⚠️"
                    quality = validation_result['quality']
                    compiles = 'Compiles' if validation_result['compiles'] else 'Broken'
                    realistic = 'Realistic' if validation_result['realistic'] else 'Unrealistic'
                    print(f"   {status} {quality} quality ({compiles}, {realistic})")

                    if not validation_result['compiles'] and validation_result['issues']:
                        print(f"   Issues: {len(validation_result['issues'])}")
                        if args.verbose:
                            for issue in validation_result['issues'][:3]:  # Show first 3 issues
                                print(f"     - {issue}")

                else:
                    print(f"   ❌ Failed: {result['error']}")

            except Exception as e:
                print(f"   ❌ Error processing {rel_path}: {str(e)}")

        # Save validation reports
        if validation_reports:
            print(f"\n📊 Saving validation reports...")
            report_dir = os.path.join(args.repo_path, args.output, "verification_report")

            for report in validation_reports:
                validator.save_validation_report(report, report_dir)

        # Print summary
        print(f"\n🎉 COMPLETED!")
        print(f"   Generated: {successful_generations}/{len(c_files)} files")
        print(f"   Tests saved to: {output_dir}")
        if validation_reports:
            print(f"   Reports saved to: {os.path.join(args.output, 'verification_report')}")

        # Overall success check
        if successful_generations == 0:
            print("❌ No tests were successfully generated")
            return 1
        elif successful_generations < len(c_files):
            print("⚠️ Some files failed to generate tests - check validation reports")
            return 1

    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    return 0


def handle_navigate(args):
    """Handle interactive navigation command"""
    print(f"🎯 Starting interactive navigation for: {args.repo_path}")

    try:
        navigator = CodeNavigator(args.repo_path)
        navigator.interactive_navigate()
    except Exception as e:
        print(f"❌ Navigation error: {e}")
        return 1

    return 0


def handle_find_func(args):
    """Handle find function command"""
    try:
        navigator = CodeNavigator(args.repo_path)
        definition = navigator.find_function_definition(args.function)

        if definition:
            rel_path = os.path.relpath(definition['file'], args.repo_path)
            print(f"📍 {args.function} defined in:")
            print(f"   File: {rel_path}")
            print(f"   Line: {definition['line']}")
            print(f"   Signature: {definition['signature']}")
        else:
            print(f"❌ Function '{args.function}' not found")
            return 1

    except Exception as e:
        print(f"❌ Error finding function: {e}")
        return 1

    return 0


def handle_find_calls(args):
    """Handle find calls command"""
    try:
        navigator = CodeNavigator(args.repo_path)
        calls = navigator.find_function_calls(args.function)

        if calls:
            print(f"📞 {args.function} is called from {len(calls)} locations:")
            for call in calls:
                rel_path = os.path.relpath(call['file'], args.repo_path)
                print(f"   {rel_path}:{call['line']} - {call['context']}")
        else:
            print(f"❌ No calls to '{args.function}' found")
            return 1

    except Exception as e:
        print(f"❌ Error finding calls: {e}")
        return 1

    return 0


def validate_environment(args):
    """Validate environment and arguments"""
    # Check repository path
    if not os.path.exists(args.repo_path):
        print(f"❌ Repository path '{args.repo_path}' does not exist")
        return False

    # Check for C files in source directory (only for generate command)
    if hasattr(args, 'source_dir'):
        source_path = os.path.join(args.repo_path, args.source_dir)
        if not os.path.exists(source_path):
            print(f"❌ Source directory '{source_path}' does not exist")
            return False

        # Check for C files
        c_files = []
        for root, dirs, files in os.walk(source_path):
            for file in files:
                if file.endswith(('.c', '.h')):
                    c_files.append(os.path.join(root, file))

        if not c_files:
            print(f"❌ No C files found in '{source_path}'")
            return False

    # Check API key (only for generate command)
    if hasattr(args, 'api_key'):
        api_key = getattr(args, 'api_key', None) or os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("❌ Set GEMINI_API_KEY environment variable or use --api-key")
            print("   Get your API key from: https://makersuite.google.com/app/apikey")
            return False

    return True


def main():
    """Main CLI entry point"""
    parser = create_parser()

    # Handle case where no arguments are provided
    if len(sys.argv) == 1:
        # No arguments provided, default to generate command
        args = parser.parse_args(['generate'])
    else:
        try:
            args = parser.parse_args()
        except SystemExit as e:
            # If parsing failed, print debug info and re-raise
            print(f"DEBUG: Failed to parse arguments: {sys.argv}", file=sys.stderr)
            print(f"DEBUG: Available commands: generate, navigate, find-func, find-calls", file=sys.stderr)
            raise

    # Default to generate command if no subcommand specified
    if getattr(args, 'command', None) is None:
        args.command = 'generate'

    # Route to appropriate handler
    if args.command == 'generate':
        sys.exit(handle_generate(args))
    elif args.command == 'navigate':
        sys.exit(handle_navigate(args))
    elif args.command == 'find-func':
        sys.exit(handle_find_func(args))
    elif args.command == 'find-calls':
        sys.exit(handle_find_calls(args))
    else:
        print(f"ERROR: Unknown command '{args.command}'", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    api_key = args.api_key or os.getenv('GEMINI_API_KEY')

    print("🚀 AI C Test Generator")
    print(f"   Repository: {args.repo_path}")
    print(f"   Source dir: {args.source_dir}")
    print(f"   Output dir: {args.output}")
    print()

    try:
        # Initialize components
        generator = SmartTestGenerator(api_key)
        validator = TestValidator(args.repo_path)

        # Build dependency map
        if args.verbose:
            print("📋 Building dependency map...")
        dependency_map = generator.build_dependency_map(args.repo_path)

        # Find C files in source directory
        source_path = os.path.join(args.repo_path, args.source_dir)
        c_files = []
        for root, dirs, files in os.walk(source_path):
            for file in files:
                if file.endswith('.c'):  # Only process .c files, not headers
                    c_files.append(os.path.join(root, file))

        if args.verbose:
            print(f"📁 Found {len(c_files)} C files to process")

        # Create output directory
        output_dir = os.path.join(args.repo_path, args.output)
        os.makedirs(output_dir, exist_ok=True)

        # Process each file
        successful_generations = 0
        validation_reports = []

        for file_path in c_files:
            rel_path = os.path.relpath(file_path, args.repo_path)
            print(f"🎯 Processing: {rel_path}")

            try:
                result = generator.generate_tests_for_file(
                    file_path, args.repo_path, output_dir, dependency_map
                )

                if result['success']:
                    print(f"   ✅ Generated: {os.path.basename(result['test_file'])}")
                    successful_generations += 1

                    # Validate the generated test
                    if args.verbose:
                        print(f"   🔍 Validating...")
                    validation_result = validator.validate_test_file(result['test_file'], file_path)
                    validation_reports.append(validation_result)

                    # Print validation summary
                    status = "✅" if validation_result['compiles'] and validation_result['realistic'] else "⚠️"
                    quality = validation_result['quality']
                    compiles = 'Compiles' if validation_result['compiles'] else 'Broken'
                    realistic = 'Realistic' if validation_result['realistic'] else 'Unrealistic'
                    print(f"   {status} {quality} quality ({compiles}, {realistic})")

                    if not validation_result['compiles'] and validation_result['issues']:
                        print(f"   Issues: {len(validation_result['issues'])}")
                        if args.verbose:
                            for issue in validation_result['issues'][:3]:  # Show first 3 issues
                                print(f"     - {issue}")

                else:
                    print(f"   ❌ Failed: {result['error']}")

            except Exception as e:
                print(f"   ❌ Error processing {rel_path}: {str(e)}")

        # Save validation reports
        if validation_reports:
            print(f"\n📊 Saving validation reports...")
            report_dir = os.path.join(args.repo_path, args.output, "verification_report")

            for report in validation_reports:
                validator.save_validation_report(report, report_dir)

        # Print summary
        print(f"\n🎉 COMPLETED!")
        print(f"   Generated: {successful_generations}/{len(c_files)} files")
        print(f"   Tests saved to: {output_dir}")
        if validation_reports:
            print(f"   Reports saved to: {os.path.join(args.output, 'verification_report')}")

        # Overall success check
        if successful_generations == 0:
            print("❌ No tests were successfully generated")
            sys.exit(1)
        elif successful_generations < len(c_files):
            print("⚠️ Some files failed to generate tests - check validation reports")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()