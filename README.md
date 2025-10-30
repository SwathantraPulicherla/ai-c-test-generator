# AI C Test Generator

AI-powered unit test generator for C code using Google Gemini AI. Automatically generates comprehensive Unity framework tests for your C functions with intelligent stub generation and validation.

## Features

- 🤖 **AI-Powered**: Uses Google Gemini 2.5 Flash for intelligent test generation
- 🔍 **Smart Analysis**: Automatically analyzes C code dependencies and function relationships
- 🧪 **Unity Framework**: Generates tests compatible with the Unity testing framework
- ✅ **Validation**: Comprehensive test validation and quality assessment
- 📊 **Reports**: Detailed validation reports with compilation status and quality metrics
- 🛠️ **CLI Tool**: Easy-to-use command-line interface
- 📦 **Pip Installable**: Install via pip for global usage

## Installation

### From PyPI (Recommended)
```bash
pip install ai-c-test-generator
```

### From Source
```bash
git clone https://github.com/your-org/ai-c-test-generator.git
cd ai-c-test-generator
pip install -e .
```

## Requirements

- Python 3.8+
- Google Gemini API key
- Unity testing framework (automatically included in generated tests)

## Quick Start

1. **Get a Gemini API Key**
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key

2. **Set Environment Variable**
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```

3. **Generate Tests**
   ```bash
   # Navigate to your C project
   cd your-c-project

   # Generate tests for all C files in src/
   ai-c-testgen

   # Or specify custom paths
   ai-c-testgen --repo-path /path/to/project --source-dir src --output tests
   ```

## Usage

### Basic Usage
```bash
ai-c-testgen [OPTIONS]
```

### Command Line Options

- `--repo-path PATH`: Path to the C repository (default: current directory)
- `--output DIR`: Output directory for generated tests (default: tests)
- `--api-key KEY`: Google Gemini API key (can also use GEMINI_API_KEY env var)
- `--source-dir DIR`: Source directory containing C files (default: src)
- `--regenerate-on-low-quality`: Automatically regenerate tests that are validated as low quality
- `--max-regeneration-attempts N`: Maximum number of regeneration attempts (default: 2)
- `--quality-threshold LEVEL`: Minimum acceptable quality threshold (**high**/medium/low, default: **high**)
- `--verbose, -v`: Enable verbose output
- `--version`: Show version information

### Examples

**Generate tests for current directory:**
```bash
ai-c-testgen
```

**Generate tests with custom paths:**
```bash
ai-c-testgen --repo-path /home/user/my-c-project --source-dir source --output test_output
```

**Use API key directly:**
```bash
ai-c-testgen --api-key YOUR_API_KEY_HERE
```

**Generate tests with strict quality requirements:**
```bash
ai-c-testgen --repo-path /path/to/project --regenerate-on-low-quality
# Only accepts high-quality tests, regenerates automatically if needed
```

## Project Structure

Your C project should follow this structure:
```
your-project/
├── src/                    # Your C source files
│   ├── main.c
│   ├── utils.c
│   └── sensors.c
├── tests/                  # Generated tests (created automatically)
│   ├── test_main.c
│   ├── test_utils.c
│   └── compilation_report/  # Validation reports
└── unity/                  # Unity framework (if not present)
```

## How It Works

1. **Code Analysis**: Scans your `src/` directory for C files
2. **Dependency Mapping**: Builds a map of function relationships across files
3. **AI Generation**: Uses Gemini AI to generate comprehensive unit tests
4. **Stub Creation**: Automatically creates stub functions for dependencies
5. **Validation**: Compiles and validates generated tests
6. **Reporting**: Saves detailed validation reports

## Generated Test Features

- **Comprehensive Coverage**: Tests normal cases, edge cases, and error conditions
- **Proper Stubs**: Automatically generated stub functions with configurable return values
- **Unity Framework**: Compatible with Unity testing framework
- **Isolation**: Each test is properly isolated with setUp/tearDown functions
- **Validation**: Tests are validated for compilation and realism

## Quality Assurance

The tool enforces **high-quality test generation** by default:

- **Default Quality Threshold**: High (only accepts tests with 0 critical issues)
- **Automatic Cleanup**: Old compilation reports are removed before each run
- **Flexible Enforcement**: 
  - **Without regeneration**: Strict - fails if quality below threshold
  - **With regeneration**: Lenient - warns but continues if max attempts exhausted
- **Strict Validation**: Tests must compile, be realistic, and follow best practices
- **Regeneration Support**: Automatically improves low-quality tests when enabled

**Quality Levels:**
- **High**: No compilation errors, realistic values, comprehensive coverage
- **Medium**: Minor issues acceptable, good coverage
- **Low**: Significant problems, requires regeneration

**Clean Report Generation:**
Each run starts with a clean slate - old validation reports are automatically removed to ensure fresh analysis.

## Automatic Regeneration

The tool can automatically regenerate low-quality tests to improve overall test quality:

```bash
# Enable automatic regeneration for low-quality tests
ai-c-testgen --regenerate-on-low-quality

# Set maximum regeneration attempts (default: 2)
ai-c-testgen --regenerate-on-low-quality --max-regeneration-attempts 3

# Only regenerate if quality is below medium threshold
ai-c-testgen --regenerate-on-low-quality --quality-threshold medium
```

**How it works:**
1. Generate initial test using AI
2. Validate test quality and compilation
3. If quality is below threshold, regenerate with improved prompts
4. Repeat up to maximum attempts or until acceptable quality is achieved
5. Report regeneration statistics and success rates

**Dynamic Feedback Loop:**
- Validation issues are fed back to the AI as specific correction instructions
- Prompts include "PREVIOUS ATTEMPT FAILED WITH THESE ISSUES - FIX THEM:" followed by actual validation errors
- AI receives targeted guidance to address compilation errors, unrealistic values, and logic issues
- Each regeneration attempt becomes more focused on fixing specific problems

**Benefits:**
- 🎯 **Higher Quality**: Automatically improves test quality through iteration
- 💰 **Cost Effective**: Only regenerates when necessary
- 📈 **Better Coverage**: AI learns from validation feedback to generate better tests
- ⚡ **Time Saving**: No manual review and regeneration cycles
- 🧠 **Intelligent Feedback**: Uses validation issues to create targeted improvement prompts

## Unity Framework Integration

The tool generates tests that work with the Unity testing framework. If Unity is not present in your project, the generated tests include the necessary framework code.

Key Unity features used:
- `TEST_ASSERT_*` macros for various assertion types
- `setUp()` and `tearDown()` functions for test isolation
- Proper test function naming (`test_*`)
- Floating-point assertions with tolerance

## API Key Setup

### Environment Variable (Recommended)
```bash
export GEMINI_API_KEY=your_api_key_here
```

### Direct Parameter
```bash
ai-c-testgen --api-key your_api_key_here
```

### .env File
Create a `.env` file in your project root:
```
GEMINI_API_KEY=your_api_key_here
```

## Troubleshooting

### Common Issues

**"No C files found"**
- Ensure your C files are in a `src/` directory
- Check that files have `.c` extension
- Use `--source-dir` to specify a different directory

**"API key not found"**
- Set the `GEMINI_API_KEY` environment variable
- Or use the `--api-key` parameter
- Check that your API key is valid

**"Compilation errors"**
- Check the validation reports in `tests/compilation_report/`
- Common issues: missing includes, incorrect function signatures
- The tool attempts to fix common issues automatically

**"Permission denied"**
- Ensure write permissions in the output directory
- Check that the repository path is accessible

### Getting Help

- Check validation reports for detailed error information
- Use `--verbose` flag for detailed output
- Ensure your C code follows standard conventions

## Development

### Setting up for Development
```bash
git clone https://github.com/your-org/ai-c-test-generator.git
cd ai-c-test-generator
pip install -e ".[dev]"
```

### Running Tests
```bash
pytest
```

### Building Distribution
```bash
python -m build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Changelog

### v1.0.0
- Initial release
- AI-powered test generation using Google Gemini
- Unity framework integration
- Comprehensive validation and reporting
- CLI tool with pip installation