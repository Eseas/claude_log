"""Setup configuration for claude-log-organizer package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="claude-log-organizer",
    version="0.1.0",
    description="Automated system for organizing Claude conversation logs into structured markdown summaries",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/claude-log-organizer",

    packages=find_packages(),
    include_package_data=True,
    package_data={"claude_log_organizer": ["signals.yaml"]},

    python_requires=">=3.8",

    install_requires=[
        "pyyaml>=6.0",
        "watchdog>=3.0.0",
        "jinja2>=3.1.0",
        "python-dateutil>=2.8.0",
        "inquirer>=3.1.0",
        "anthropic>=0.18.0",
        "rich>=13.0.0",
        "typer>=0.9.0",
    ],

    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.0",
            "black>=23.7.0",
            "flake8>=6.1.0",
        ],
    },

    entry_points={
        "console_scripts": [
            "claude-log-organizer=claude_log_organizer.cli:main",
            "claude-log-organizer-interactive=claude_log_organizer.interactive:main",
        ],
    },

    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
