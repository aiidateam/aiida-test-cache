===========================
Using :mod:`.archive_cache`
===========================

:mod:`.archive_cache` provides three central fixtures 

- :py:func:`~aiida_testing.archive_cache.create_node_archive` and :py:func:`~aiida_testing.archive_cache.load_node_archive` are used to manage AiiDA archive test files in the pytest environment
- :py:func:`~aiida_testing.archive_cache.enable_archive_cache` uses the above fixtures and the AiiDA caching mechanisms to enable end-to-end tests of high-level workchains without going through executing individual `Calcjob` processes

Here an example for using the :py:func:`~aiida_testing.archive_cache.enable_archive_cache` to test a simple workchain using the ``diff`` code

The workchain looks as follows

.. code-block:: python

    class DiffWorkChain(WorkChain):
    """
    Very simple workchain which wraps a diff calculation for testing purposes
    """

    @classmethod
    def define(cls, spec):
        super(DiffWorkChain, cls).define(spec)
        spec.expose_inputs(DiffCalculation, namespace='diff')
        spec.outline(
            cls.rundiff,
            cls.results,
        )
        spec.output('computed_diff')

    def rundiff(self):
        inputs = self.exposed_inputs(DiffCalculation, 'diff')
        running = self.submit(DiffCalculation, **inputs)

        return ToContext(diff_calc=running)

    def results(self):
        computed_diff = self.ctx.diff_calc.get_outgoing().get_node_by_label('diff')
        self.out('computed_diff', computed_diff)


And an example of using the above fixtures in a pytest test suite looks as follows

.. code-block:: python

    def test_diff_workchain(enable_archive_cache):
        """
        End to end test of DiffWorkchain
        """
        # ... set up test inputs

        inputs = {
            'diff': {
                'code': diff_code,
                'parameters': parameters,
                'file1': file1,
                'file2': file2,
            }
        }
    with enable_archive_cache('diff_workchain.aiida'):
        res, node = run_get_node(DiffWorkChain, **inputs)

    # Test results of workchain

The fixture will look for the AiiDA archive named ``diff_workchain.aiida`` in a folder named ``caches`` in the same directory as the test file, if nothing else is specified.
If this exists the archive is imported and the AiiDA caching functionality is enabled. All calculations created inside the with block will use the cached nodes if their
inputs and attributes match.
If the archive does not exist the workchain will try to run the complete calculation.

.. note::
    The caching mechanism of AiiDA is modified within test functions using these fixtures to ignore attributes, that would break the
    caching if the tests are run on different machines with different versions of AiiDA for example
    By default the stored test caches are also migrated to match the installed AiiDA version


The following options can be specified in the ``aiida-testing-config.yml`` file

.. code-block:: yaml

    archive_cache:
        default_data_dir: ... #If specified all relative paths passed to enable_archive_cache are relative to this
        ignore:
            calcjob_inputs: [...] #List of link labels of inputs to ignore in the aiida hash
            calcjob_attributes: [...] #List of attributes of CalcjobNodes to ignore in the aiida hash
            node_attributes: #mapping of entry points to list of attributes to ignore in hashing of nodes with those entry points
                diff: [..]

.. note::
    The file location of the archives used for these regression tests can be specified as the first argument to the
    :py:func:`~aiida_testing.archive_cache.enable_archive_cache` and can either be an absolute or relative file path
    for an AiiDA archive file

    If the path is absolute it will be used directly. A relative path is interpreted with respect to either the
    ``default_data_dir`` option in the config file, or if this option isn't specified a folder named ``caches`` in
    the same directory as the test file in question

    So in the default case providing just the name of the archive to :py:func:`~aiida_testing.archive_cache.enable_archive_cache`
    will create an archive with the given name in the ``caches`` subfolder


.. code-block:: bash

    $ pytest -h
    ...
    custom options:
      --archive-cache-forbid-migration
                            If True the stored archives cannot be migrated
                            if their versions are incompatible.

