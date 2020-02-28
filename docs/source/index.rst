.. figure:: images/AiiDA_transparent_logo.png
    :width: 250px
    :align: center

The aiida-testing pytest plugin
===============================

A pytest plugin to simplify testing of `AiiDA`_ plugins. It implements
fixtures to cache the execution of codes:

* :mod:`.mock_code`: Caches at the level of the code executable. Use this for
  testing calculation and parser plugins, because input file generation
  and output parsing are also being tested.
* :mod:`.archive_cache`: Uses the AiiDA caching feature, in combination with
  an automatic archive creation/loading. Use this to test high-level
  workflows.

``aiida-testing`` is available at http://github.com/aiidateam/aiida-testing


.. toctree::
   :maxdepth: 2

   user_guide/index
   developer_guide/index
   API documentation <apidoc/aiida_testing>

If you use `AiiDA`_ for your research, please cite the following work:

.. highlights:: Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari,
  and Boris Kozinsky, *AiiDA: automated interactive infrastructure and database
  for computational science*, Comp. Mat. Sci 111, 218-230 (2016);
  https://doi.org/10.1016/j.commatsci.2015.09.013; http://www.aiida.net.

``aiida-testing`` is released under the Apache license.




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _AiiDA: http://www.aiida.net
