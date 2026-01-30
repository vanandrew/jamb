[![CI](https://github.com/vanandrew/jamb/actions/workflows/ci.yml/badge.svg)](https://github.com/vanandrew/jamb/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/vanandrew/jamb/graph/badge.svg?token=RL7H4DG3YO)](https://codecov.io/gh/vanandrew/jamb)
[![PyPI - Version](https://img.shields.io/pypi/v/jamb?style=flat)](https://pypi.org/project/jamb/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/jamb?style=flat)](https://pypi.org/project/jamb/)
[![PyPI - License](https://img.shields.io/pypi/l/jamb?style=flat)](https://pypi.org/project/jamb/)
[![Docs](https://readthedocs.org/projects/jamb/badge/?version=latest)](https://jamb.readthedocs.io)

# jamb

IEC 62304 requirements traceability for pytest.

jamb links your pytest tests to requirements, generating traceability matrices for regulatory submissions. It's designed for medical device software and other regulated industries where you need to prove every requirement has been tested.

## Installation

```bash
pip install jamb
```

## Quick Example

```bash
# Initialize a project with IEC 62304 documents
jamb init

# Add and link requirements
jamb item add SRS
jamb item edit SRS001
jamb link add SRS001 SYS001
```

```python
import pytest

@pytest.mark.requirement("SRS001")
def test_valid_credentials():
    assert authenticate("admin", "secret") is True
```

```bash
# Generate traceability matrix
pytest --jamb --jamb-trace-matrix matrix.html
```

## Documentation

Full documentation is available at [jamb.readthedocs.io](https://jamb.readthedocs.io).

- [Quickstart](https://jamb.readthedocs.io/en/latest/getting-started/quickstart.html) -- get up and running
- [Concepts](https://jamb.readthedocs.io/en/latest/user-guide/concepts.html) -- suspect links, review cycles, document hierarchy
- [Configuration](https://jamb.readthedocs.io/en/latest/user-guide/configuration.html) -- `pyproject.toml` and document settings
- [pytest Integration](https://jamb.readthedocs.io/en/latest/user-guide/pytest-integration.html) -- markers, options, and matrix formats
- [CI/CD](https://jamb.readthedocs.io/en/latest/user-guide/ci-cd.html) -- GitHub Actions, pre-commit hooks
