# Quickstart

Get up and running with jamb in five minutes.

## 1. Initialize a Project

```bash
mkdir my-project && cd my-project
git init
jamb init
```

This creates a `reqs/` folder with the standard IEC 62304 document hierarchy:

```
PRJ (Project Requirements) - root
├── UN (User Needs)
│   └── SYS (System Requirements)
│       └── SRS (Software Requirements Specification)
└── HAZ (Hazards)
    └── RC (Risk Controls)
        └── SRS (also traces to RC)
```

## 2. Add Requirements

```bash
# Add a user need
jamb item add UN
jamb item edit UN001

# Add a system requirement and link it
jamb item add SYS
jamb item edit SYS001
jamb link add SYS001 UN001

# Add a software requirement and link it
jamb item add SRS
jamb item edit SRS001
jamb link add SRS001 SYS001
```

## 3. Write a Test

Create `tests/test_example.py`:

```python
import pytest

@pytest.mark.requirement("SRS001")
def test_my_requirement():
    # Your test logic here
    assert True
```

## 4. Check Coverage

```bash
# Static check (no test execution)
jamb check

# Run tests with traceability
pytest --jamb
```

## 5. Generate a Traceability Matrix

```bash
pytest --jamb --jamb-trace-matrix matrix.html
```

Open `matrix.html` in a browser to see which requirements have passing tests.

For IEC 62304 compliant test records, include tester and version metadata:

```bash
pytest --jamb --jamb-trace-matrix matrix.html \
    --jamb-tester-id "CI Pipeline" \
    --jamb-software-version "1.0.0"
```

The matrix includes software version, tester ID, execution timestamp, and test environment details.

## 6. Validate the Requirements Tree

```bash
jamb validate
```

This checks for broken links, cycles, suspect links, and missing reviews.

## Next Steps

- Read the full {doc}`tutorial` for a complete walkthrough
- Learn about {doc}`/user-guide/concepts` like suspect links and review cycles
- See all CLI commands in the {doc}`/user-guide/commands`
- Set up {doc}`/user-guide/ci-cd` to enforce traceability in your pipeline
