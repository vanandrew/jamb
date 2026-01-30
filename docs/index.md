# <img src="_static/icon-light.svg" alt="jamb icon" width="40" style="vertical-align: middle;" class="only-light"><img src="_static/icon-dark.svg" alt="jamb icon" width="40" style="vertical-align: middle;" class="only-dark"> jamb

**IEC 62304 requirements traceability for pytest.**

jamb links your pytest tests to requirements, generating traceability matrices for regulatory submissions. It's designed for medical device software and other regulated industries where you need to prove every requirement has been tested.

## Features

jamb treats requirements as code: you store them as YAML files in your git repository and link tests to them with `@pytest.mark.requirement`, so traceability lives alongside the source it describes. It generates traceability matrices in HTML, Markdown, JSON, CSV, and Excel, and automatically flags downstream items as suspect when an upstream requirement changes. Built-in review workflows track review status and enforce review cycles, while validation catches broken links, cycles, and orphan items. The default document hierarchy follows IEC 62304, and every check runs in CI/CD so your pipeline can enforce traceability on every commit.

:::{note}
jamb focuses on **requirements traceability and test coverage** — linking requirements to each other and to pytest tests, then generating the evidence artifacts. It does not provide project management, document control, risk analysis worksheets, electronic signatures, or other ALM capabilities. Teams typically use jamb alongside a QMS and risk management process (see {doc}`iec-62304/overview`).
:::

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
pytest --jamb --jamb-trace-matrix matrix.html
```

### Trace Matrix

Full traceability chains from user needs through system and software requirements to tests:

```{image} _static/trace-matrix-screenshot.png
:alt: Example traceability matrix showing requirement chains
```

### Test Records Matrix

Test-centric view with actions, expected/actual results for IEC 62304 compliance:

```{image} _static/test-records-screenshot.png
:alt: Example test records matrix with test actions and results
```

### Requirements Documents

You can also publish requirements documents as standalone HTML, Markdown, or Word files:

```bash
jamb publish SRS docs/srs.html
```

```{image} _static/publish-example.png
:alt: Example published requirements document
```

```{toctree}
:maxdepth: 1
:hidden:

getting-started/index
user-guide/index
iec-62304/index
api/index
faq
troubleshooting
```
