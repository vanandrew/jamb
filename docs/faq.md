# FAQ

## How does jamb compare to doorstop?

Both tools store requirements as individual YAML files in git and detect suspect links via content hashing. The main differences:

**jamb advantages**

- Native pytest integration (`@pytest.mark.requirement`, `jamb_log`, auto-generated matrices from test runs)
- DAG document hierarchy (multiple parents per document vs doorstop's strict tree)
- IEC 62304 scaffolding (`jamb init`)
- `pyproject.toml` configuration

**doorstop advantages**

- Desktop GUI and web server
- LaTeX/PDF publishing
- Longer track record (~10+ years, larger community)

In short, jamb is designed around the pytest workflow; doorstop is a more general-purpose requirements management tool.

## What standards does jamb support?

The built-in `jamb init` command creates an IEC 62304 hierarchy, but the document/item/link model is generic enough for any standard requiring traceability (IEC 62443, DO-178C, ISO 26262, etc.).

## Do I need to use `jamb init`?

No — you can create custom document hierarchies with `jamb doc create`.

## Can an item link to multiple parent documents?

Yes — jamb uses a DAG, so both items and documents support multiple parents.

## What happens when I edit a requirement?

Downstream links become suspect. `jamb validate` flags them, and reviewers clear them with `jamb review mark` followed by `jamb review clear`.

## Can I use jamb without pytest?

Yes — CLI commands (`jamb validate`, `jamb check`, `jamb publish`) work standalone. The pytest integration is optional.
