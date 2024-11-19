.. figure:: images/AiiDA_transparent_logo.png
    :width: 250px
    :align: center

aiida-test-cache pytest plugin
==================================

A pytest plugin to simplify testing of `AiiDA`_ workflows. It implements
fixtures to cache the execution of codes:

* :mod:`.mock_code`: Caches at the level of the code executable. Use this for
  testing calculation and parser plugins, because input file generation
  and output parsing are also being tested.
* :mod:`.archive_cache`: Uses the AiiDA caching feature, in combination with
  an automatic archive creation/loading. Use this to test high-level
  workflows.

``aiida-test-cache`` is available at http://github.com/aiidateam/aiida-test-cache


.. toctree::
   :maxdepth: 2

   user_guide/index
   developer_guide/index
   API documentation <apidoc/aiida_test_cache>

If you use `AiiDA`_ for your research, please cite the following work:

.. highlights:: Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari,
  and Boris Kozinsky, *AiiDA: automated interactive infrastructure and database
  for computational science*, Comp. Mat. Sci 111, 218-230 (2016);
  https://doi.org/10.1016/j.commatsci.2015.09.013; http://www.aiida.net.

``aiida-test-cache`` is released under the MIT license.




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _AiiDA: http://www.aiida.net
