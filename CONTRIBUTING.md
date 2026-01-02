# Contributing to Stegasoo

Thank you for your interest in contributing to Stegasoo! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Docker (optional, for container testing)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/adlee-was-taken/stegasoo.git
   cd stegasoo
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

## Development Workflow

### Code Style

We use the following tools to maintain code quality:

- **Black** - Code formatting (line length: 100)
- **Ruff** - Linting
- **MyPy** - Type checking

Run all checks before committing:
```bash
black src/ tests/ frontends/
ruff check src/ tests/ frontends/
mypy src/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=stegasoo --cov-report=term-missing

# Run specific test file
pytest tests/test_stegasoo.py
```

### Type Hints

All new code should include type hints:

```python
def encode_message(
    message: str,
    carrier_image: bytes,
    passphrase: str,
    pin: str = "",
) -> EncodeResult:
    ...
```

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages

Write clear, concise commit messages:

```
Add channel key validation for private messaging

- Implement validate_channel_key() function
- Add tests for valid/invalid key formats
- Update CLI to support --channel-key flag
```

### Pull Request Process

1. **Create a feature branch** from `main`
2. **Make your changes** with appropriate tests
3. **Ensure all checks pass** (tests, linting, formatting)
4. **Submit a PR** with a clear description
5. **Address review feedback** promptly

### PR Checklist

- [ ] Tests added/updated for changes
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated for user-facing changes
- [ ] All CI checks passing
- [ ] No merge conflicts with `main`

## Project Structure

```
stegasoo/
├── src/stegasoo/       # Core library
│   ├── crypto.py       # Encryption/decryption
│   ├── steganography.py # LSB embedding
│   ├── dct_steganography.py # DCT embedding
│   └── ...
├── frontends/
│   ├── cli/            # Command-line interface
│   ├── web/            # Flask web UI
│   └── api/            # FastAPI REST API
├── tests/              # Test suite
└── examples/           # Usage examples
```

## Reporting Issues

### Bug Reports

Please include:
- Python version and OS
- Stegasoo version (`stegasoo --version`)
- Minimal reproduction steps
- Expected vs actual behavior
- Error messages/tracebacks

### Feature Requests

Please include:
- Use case description
- Proposed solution (if any)
- Alternatives considered

## Security

If you discover a security vulnerability, please see [SECURITY.md](SECURITY.md) for responsible disclosure guidelines. **Do not open a public issue for security vulnerabilities.**

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open a discussion or issue if you have questions about contributing.

Thank you for helping make Stegasoo better!
