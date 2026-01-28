Storage
=======

Native file-based storage layer for requirements documents and items.

Document DAG
------------

.. module:: jamb.storage.document_dag

.. autoclass:: DocumentDAG
   :members:

Document Configuration
----------------------

.. module:: jamb.storage.document_config

.. autoclass:: DocumentConfig
   :members:

.. autofunction:: load_document_config

.. autofunction:: save_document_config

Discovery
---------

.. module:: jamb.storage.discovery

.. autofunction:: discover_documents

Graph Builder
-------------

.. module:: jamb.storage.graph_builder

.. autofunction:: build_traceability_graph

Items
-----

.. module:: jamb.storage.items

.. autofunction:: read_item

.. autofunction:: read_document_items

.. autofunction:: compute_content_hash

.. autofunction:: write_item

.. autofunction:: next_uid

.. autofunction:: dump_yaml

Validation
----------

.. module:: jamb.storage.validation

.. autoclass:: ValidationIssue
   :members:

.. autofunction:: validate

Reorder
-------

.. module:: jamb.storage.reorder

.. autofunction:: reorder_document

.. autofunction:: insert_items
