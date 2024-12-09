=======================
Using :mod:`.mock_code`
=======================

:mod:`.mock_code` provides two components:

 1. A command-line script ``aiida-mock-code`` (the *mock executable*) that is executed instead of the *actual* executable and acts as a *cache* for the outputs of the actual executable

 2. A pytest fixture :py:func:`~aiida_test_cache.mock_code.mock_code_factory` that sets up an AiiDA InstalledCode pointing to the mock executable

In the following, we will set up a mock code for the ``diff`` executable in three simple steps.

First, we want to define a fixture for our mocked code in the ``conftest.py``:

.. code-block:: python

    import os
    import pytest

    # Directory where to store outputs for known inputs (usually tests/data)
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    @pytest.fixture(scope='function')
    def mocked_diff(mock_code_factory):
        """
        Create mocked "diff" code 
        """
        return mock_code_factory(
            label='diff',
            data_dir_abspath=DATA_DIR,
            entry_point='diff',
            # files *not* to copy into the data directory
            ignore_paths=('_aiidasubmit.sh', 'file*')
        )

Second, we need to tell the mock executable where to find the *actual* ``diff`` executable by creating a ``.aiida-test-cache-config.yml`` file in the top level of our plugin.

.. note::
    This step is needed **only** when we want to use the actual executable to (re)generate test data.
    As long as the mock code receives data inputs whose corresponding outputs have already been stored in the data directory, the actual executable is not used.

.. code-block:: yaml

    mock_code:
      # code-label: absolute path
      diff: /usr/bin/diff


.. note::
   Why yet another configuration file?

   The location of the actual executables will differ from one computer to the next, so hardcoding their location is not an option.
   Even the names of the executables may differ, making searching for executables in the PATH fragile.
   Finally, one could use dedicated environment variables to specify the locations of the executables, but there may be many of them, making this approach cumbersome.
   Ergo, a configuration file.

Finally, we can use our fixture in our tests as if it would provide a normal :py:class:`~aiida.orm.InstalledCode`:

.. code-block:: python

    def test_diff(mocked_diff):
        # ... set up test inputs

        inputs = {
            'code': mocked_diff,
            'parameters': parameters,
            'file1': file1,
            'file2': file2,
        }
        results, node = run_get_node(CalculationFactory('diff'), **inputs)
        assert node.is_finished_ok

When running the test via ``pytest`` for the first time, ``aiida-mock-code`` will pipe through to the actual ``diff`` executable.
The next time, it will recognise the inputs and directly use the outputs cached in the data directory.

.. note::
    ``aiida-mock-code`` "recognizes" calculations by computing a hash of the working directory of the calculation (as prepared by the calculation input plugin).
    It does *not* rely on the hashing mechanism of AiiDA.


Running continuous integration (CI) tests on your repository:

 - Don't forget to commit changes to your data directory to make the cache available on CI
 - Run tests on CI with ``pytest --mock-fail-on-missing`` to force a test failure when it fails when the committed cache is incomplete

Since the ``.aiida-test-cache-config.yml`` file is usually specific to your machine, there is no need to commit it.
As long as the test cache is complete, tests will run fine without it, and if other developers need to change test inputs, they can easily regenerate a template for it using ``pytest --testing-config-action=generate``.

For further documentation on the pytest commandline options added by mock code, see:

.. code-block:: bash

    $ pytest -h
    ...
    custom options:
      --testing-config-action=TESTING_CONFIG_ACTION
                            Read .aiida-test-cache-config.yml config file if present
                            ('read'), require config file ('require') or generate
                            new config file ('generate').
      --mock-regenerate-test-data
                            Regenerate test data.

      --mock-fail-on-missing
                            Fail if cached data is not found, rather than regenerating it.
      --mock-disable-mpi    Run all calculations with `metadata.options.usempi=False`.

Limitations
-----------

 * No support for remote codes yet
 * Not tested with MPI
