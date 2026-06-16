Publishing
==========

Document rendering for regulatory submissions, built on Quarto.

Document model
--------------

.. module:: jamb.publish.document

.. autofunction:: build_publish_document

.. autoclass:: PublishDocument

.. autoclass:: RenderSection

.. autoclass:: RenderItem

Quarto source
-------------

.. module:: jamb.publish.qmd

.. autofunction:: render_qmd

Formats
-------

.. module:: jamb.publish.formats

.. autoclass:: OutputFormat

.. autofunction:: format_from_path

Rendering
---------

.. module:: jamb.publish.render

.. autofunction:: render_document

.. module:: jamb.publish.quarto

.. autofunction:: find_quarto

.. autofunction:: quarto_version
