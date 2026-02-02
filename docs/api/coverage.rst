Coverage Serialization
======================

Save and load coverage data for decoupled matrix generation.

The coverage module provides functions to persist test coverage data to disk
(as ``.jamb`` files) and reload it later. This enables workflows where tests
are run once and matrices are regenerated multiple times without re-running
tests.

Constants
---------

.. module:: jamb.coverage

.. data:: COVERAGE_FILE

   Default filename for coverage data: ``.jamb``

Functions
---------

.. autofunction:: save_coverage

.. autofunction:: load_coverage

File Format
-----------

The ``.jamb`` file is a JSON document containing:

- **version**: File format version (for forward compatibility)
- **coverage**: Dict mapping item UIDs to coverage data (item details and linked tests)
- **graph**: Full traceability graph with all items and relationships
- **metadata**: Optional IEC 62304 metadata (tester ID, timestamps, environment)
- **manual_tc_ids**: Optional dict mapping test nodeids to manual TC IDs

This file is automatically created by ``pytest --jamb`` and consumed by
``jamb matrix`` to regenerate matrices without re-running tests.
