# <img src="_static/icon-light.svg" alt="jamb icon" width="40" style="vertical-align: middle;" class="only-light"><img src="_static/icon-dark.svg" alt="jamb icon" width="40" style="vertical-align: middle;" class="only-dark"> jamb

**IEC 62304 requirements traceability for pytest.**

jamb links your pytest tests to requirements, generating traceability matrices for regulatory compliance. It's designed for medical device software and other regulated industries where you need to prove every requirement has been tested.

## Features

jamb treats requirements as code: you store them as YAML files in your git repository and link tests to them with `@pytest.mark.requirement`, so traceability lives alongside the source it describes. It generates traceability matrices in HTML, Markdown, JSON, CSV, and Excel, and automatically flags downstream items as suspect when an upstream requirement changes. Built-in review workflows track review status and enforce review cycles, while validation catches broken links, cycles, orphan items, and missing coverage. The default document hierarchy follows IEC 62304, and every check runs in CI/CD so your pipeline can enforce traceability on every commit.

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
troubleshooting
```
