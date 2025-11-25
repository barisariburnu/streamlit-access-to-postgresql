# Contributing to MDB to PostgreSQL

First off, thank you for considering contributing to MDB to PostgreSQL! It's people like you that make this tool better for everyone.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Pull Requests](#pull-requests)
- [Development Setup](#development-setup)
- [Style Guidelines](#style-guidelines)
  - [Git Commit Messages](#git-commit-messages)
  - [Python Style Guide](#python-style-guide)

## Code of Conduct

This project and everyone participating in it is governed by our commitment to providing a welcoming and inspiring community for all. Please be respectful and constructive in your communications.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title** for the issue
* **Describe the exact steps to reproduce the problem**
* **Provide specific examples** to demonstrate the steps
* **Describe the behavior you observed** and what behavior you expected to see
* **Include screenshots** if relevant
* **Include your environment details**: OS, Python version, PostgreSQL version, Docker version

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a detailed description** of the suggested enhancement
* **Explain why this enhancement would be useful** to most users
* **List any alternative solutions** you've considered

### Pull Requests

* Fill in the required template
* Follow the [Python style guide](#python-style-guide)
* Include appropriate test cases
* Update documentation as needed
* End all files with a newline

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/barisariburnu/mdb-to-postgresql.git
   cd mdb-to-postgresql
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up configuration**
   ```bash
   mkdir .streamlit
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # Edit .streamlit/secrets.toml with your PostgreSQL credentials
   ```

5. **Run the application**
   ```bash
   streamlit run app.py
   ```

## Style Guidelines

### Git Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests after the first line
* Consider starting the commit message with an applicable emoji:
  * 🎨 `:art:` when improving the format/structure of the code
  * 🐛 `:bug:` when fixing a bug
  * ✨ `:sparkles:` when adding a new feature
  * 📝 `:memo:` when writing docs
  * 🔧 `:wrench:` when updating configuration files
  * ♻️ `:recycle:` when refactoring code
  * ✅ `:white_check_mark:` when adding tests
  * 🔒 `:lock:` when dealing with security

### Python Style Guide

* Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
* Use 4 spaces for indentation
* Use meaningful variable and function names
* Add docstrings to all functions and classes
* Keep functions focused and small
* Use type hints where appropriate
* Write comments for complex logic

**Example:**

```python
def process_data(input_data: List[str]) -> Dict[str, Any]:
    """
    Process input data and return structured results.
    
    Args:
        input_data: List of strings to process
        
    Returns:
        Dictionary containing processed results
    """
    # Implementation here
    pass
```

## Testing

Before submitting a pull request:

1. Test your changes thoroughly
2. Ensure all existing functionality still works
3. Test with different database configurations
4. Test with various MDB file sizes and structures

## Questions?

Feel free to open an issue with your question or reach out to the maintainers.

---

Thank you for contributing! 🎉
