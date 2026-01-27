# jamb

**IEC 62304 requirements traceability for pytest.**

jamb links your pytest tests to requirements, generating traceability matrices for regulatory compliance. It's designed for medical device software and other regulated industries where you need to prove every requirement has been tested.

## Features

- **Requirements as code** -- store requirements as YAML files in your git repository
- **pytest integration** -- link tests to requirements with `@pytest.mark.requirement`
- **Traceability matrices** -- generate HTML, Markdown, JSON, CSV, or Excel matrices
- **Suspect link detection** -- automatically flag downstream items when upstream requirements change
- **Review workflows** -- track review status and enforce review cycles
- **Validation** -- check for broken links, cycles, orphan items, and missing coverage
- **IEC 62304 hierarchy** -- built-in support for the standard medical device document hierarchy
- **CI/CD ready** -- run validation and coverage checks in your pipeline

## Quick Example

```bash
# Initialize a project with IEC 62304 documents
jamb init

# Add and link requirements
jamb item add SRS
jamb item edit SRS001
jamb link add SRS001 SYS001

# Link a test
# tests/test_example.py
# @pytest.mark.requirement("SRS001")
# def test_something(): ...

# Generate traceability matrix
pytest --jamb --jamb-matrix matrix.html
```

```{toctree}
:maxdepth: 2
:caption: Contents

getting-started/index
user-guide/index
iec-62304/index
api/index
faq
```
