pytest Plugin
=============

pytest integration for requirements traceability.

Plugin Hooks
------------

.. module:: jamb.pytest_plugin.plugin

.. autofunction:: pytest_addoption

.. autofunction:: pytest_configure

.. autofunction:: pytest_sessionfinish

.. autofunction:: jamb_log

Collector
---------

.. module:: jamb.pytest_plugin.collector

.. autoclass:: RequirementCollector
   :members:

Markers
-------

.. module:: jamb.pytest_plugin.markers

.. autofunction:: get_requirement_markers

JambLog
-------

.. module:: jamb.pytest_plugin.log

.. autoclass:: JambLog
   :members:
