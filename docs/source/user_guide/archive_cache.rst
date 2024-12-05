===========================
Using :mod:`.archive_cache`
===========================

:mod:`.archive_cache` provides the :py:func:`~aiida_test_cache.archive_cache.enable_archive_cache` pytest fixture. It uses the AiiDA caching mechanisms to enable end-to-end tests of high-level workchains without executing individual `Calcjob` processes, if they can be cached from a stored archive.

Here an example of using the :py:func:`~aiida_test_cache.archive_cache.enable_archive_cache` fixture to test a simple workchain using the ``diff`` code

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
        computed_diff = self.ctx.diff_calc.base.links.get_outgoing().get_node_by_label('diff')
        self.out('computed_diff', computed_diff)


And here is the test

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
If the archive does not exist the, workchain will try to run the complete calculation and, afterwards, create the archive in the specified location.

.. note::
    The hashing mechanism of AiiDA is modified within tests that use the fixture to ignore certain attributes that would invalidate the
    cache when running the tests on different machines, with different versions of AiiDA, etc.
    By default, the test archives are migrated to match the installed AiiDA version.


The following options can be specified in the ``.aiida-testing-config.yml`` file. All of the below options are optional and do not need to be modified in order to use
the archive cache functionalities

.. code-block:: yaml

    archive_cache:
        default_data_dir: ... #If specified all relative paths passed to enable_archive_cache are relative to this
        ignore:
            calcjob_inputs: [...] #List of link labels of inputs to ignore in the aiida hash
            calcjob_attributes: [...] #List of attributes of CalcjobNodes to ignore in the aiida hash
            node_attributes: #mapping of entry points to list of attributes to ignore in hashing of nodes with those entry points
                diff: [..]

An example, where it might be necessary to modify the options in the ``ignore`` namespace, is testing workchains across multiple AiiDA core versions.
When using a AiiDA archive created in version ``1.6`` and testing the workchain with this archive in version ``2.X``, calcjob nodes contain new metadata
attributes (in this case ``environment_variables_double_quotes``). Therefore, in order to still reuse the ``1.6`` archive the added attributes have to
be ignored when computing the hash of this calcjob. 

.. note::
    The file location of the archives used for these regression tests can be specified as the first argument to the
    :py:func:`~aiida_test_cache.archive_cache.enable_archive_cache` and can either be an absolute or relative file path
    for an AiiDA archive file

    If the path is absolute it will be used directly. A relative path is interpreted with respect to either the
    ``default_data_dir`` option in the config file, or if this option isn't specified a folder named ``caches`` in
    the same directory as the test file in question

    So in the default case providing just the name of the archive to :py:func:`~aiida_test_cache.archive_cache.enable_archive_cache`
    will create an archive with the given name in the ``caches`` subfolder


.. code-block:: bash

    $ pytest -h
    ...
    custom options:
      --archive-cache-forbid-migration
                            If True the stored archives cannot be migrated
                            if their versions are incompatible.
      --archive-cache-overwrite
                            If True the stored archives are overwritten
                            with the archive created by the current test run.

