# FAQ

## How does jamb compare to doorstop?

You may notice some similarities between jamb and [doorstop](https://doorstop.readthedocs.io/en/latest/).

`jamb` started as an extension to `doorstop`, but I found the doorstop's tree architecture limiting for certain use cases.

Both tools store requirements as individual YAML files in git and detect suspect links via content hashing. The main differences:

jamb's main strengths are its native pytest integration (`@pytest.mark.requirement`, `jamb_log`, auto-generated matrices from test runs), a DAG document hierarchy that allows multiple parents per document instead of doorstop's strict tree, IEC 62304 scaffolding via `jamb init`, and `pyproject.toml`-based configuration.

doorstop offers a desktop GUI and web server, LaTeX/PDF publishing, and a longer track record (~10+ years, larger community).

In short, jamb is designed around the pytest workflow; doorstop is a more general-purpose requirements management tool.

## Is jamb a full ALM or compliance solution?

No. jamb handles **requirements traceability and test coverage** — it links requirements to each other and to pytest tests, validates the traceability chain, and generates matrices and published documents. It does not provide:

- Risk analysis worksheets or probability/severity scoring (ISO 14971)
- Quality management system processes (ISO 13485)
- Electronic signatures or 21 CFR Part 11 compliance
- Project planning, issue tracking, or workflow automation
- Design documentation or architecture management
- Configuration management beyond what git provides

jamb's HAZ and RC document types support **risk-to-requirement traceability** (linking hazards to risk controls to software requirements), but the full risk management process — hazard analysis, risk estimation, residual risk evaluation, benefit-risk analysis — must be handled by your risk management process and tools.

For early-stage teams, jamb can serve as your traceability tool while you use simpler methods (spreadsheets, documents) for risk management and QMS. As your team and regulatory needs grow, you may add a commercial ALM for cross-functional workflows while continuing to use jamb for developer-facing traceability.

## What standards does jamb support?

The built-in `jamb init` command creates an IEC 62304 hierarchy, but the document/item/link model is generic enough for the **traceability requirements** of other standards (IEC 62443, DO-178C, ISO 26262, etc.).

## Do I need to use `jamb init`?

No — you can create custom document hierarchies with `jamb doc create`.

## Can an item link to multiple parent documents?

Yes — jamb uses a DAG, so both items and documents support multiple parents.

## What happens when I edit a requirement?

Downstream links become suspect. `jamb validate` flags them, and reviewers clear them with `jamb review mark` followed by `jamb review clear`.

## Can I use jamb without pytest?

Yes — CLI commands (`jamb validate`, `jamb check`, `jamb publish`) work standalone. The pytest integration is optional.

## Can I use jamb for non-medical device standards?

Yes. While `jamb init` scaffolds an IEC 62304 hierarchy, the underlying document/item/link model is standard-agnostic. You can create custom document hierarchies with `jamb doc create` to match any standard that requires requirements traceability, such as IEC 62443 (industrial cybersecurity), DO-178C (airborne software), or ISO 26262 (automotive safety).

## What test documents does jamb check by default?

When no `test_documents` are configured in `pyproject.toml`, jamb defaults to checking **leaf documents** — documents that are not parents of any other document. In the standard IEC 62304 hierarchy, these are SRS. You can override this by setting `test_documents` in `[tool.jamb]` in your `pyproject.toml`:

```toml
[tool.jamb]
test_documents = ["SRS", "SYS"]
```

Or use the `--jamb-documents` flag with pytest: `pytest --jamb --jamb-documents SRS,SYS`

## How large a project can jamb handle?

jamb stores each item as an individual YAML file on disk, so disk I/O scales linearly with the number of items. When you run `jamb validate`, `jamb check`, or `pytest --jamb`, jamb reads every item file and builds an in-memory traceability graph. This means memory usage and build time grow linearly with the total number of items and links.

In practice, projects with hundreds to low thousands of requirements work well. If your project is very large, you can use the `exclude_patterns` configuration option in `[tool.jamb]` to limit which documents are loaded:

```toml
[tool.jamb]
exclude_patterns = ["ARCHIVE/*", "LEGACY/*"]
```

You can also scope validation and coverage checks to specific documents using `--documents` or `--skip` flags:

```bash
jamb validate --skip LEGACY
jamb check --documents SRS,SYS
```
