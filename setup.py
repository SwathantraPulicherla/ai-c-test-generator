"""
Setup script for AI C Test Generator
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ai-c-test-generator",
    version="1.0.0",
    author="AI Test Generator Team",
    author_email="testgen@example.com",
    description="AI-powered C unit test generator using Google Gemini",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/ai-c-test-generator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Code Generators",
    ],
    python_requires=">=3.8",
    install_requires=[
        "google-generativeai>=0.8.0",
        "python-dotenv>=0.19.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-c-testgen=ai_c_test_generator.cli:main",
        ],
    },
    keywords="c testing unit-tests ai gemini code-generation",
    project_urls={
        "Bug Reports": "https://github.com/your-org/ai-c-test-generator/issues",
        "Source": "https://github.com/your-org/ai-c-test-generator",
    },
)