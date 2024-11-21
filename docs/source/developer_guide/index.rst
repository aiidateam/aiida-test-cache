===============
Developer guide
===============

Full setup
++++++++++

The following commands give you a complete development setup for
``aiida-test-cache``.
Make sure to run this in the appropriate virtual environment::

    git clone https://github.com/aiidateam/aiida-test-cache.git
    cd aiida-test-cache
    pip install -e .[dev]
    pre-commit install

Commands to install only parts of the development setup are included
below.

Running the tests
+++++++++++++++++

The following will discover and run all unit tests::

    pip install -e .[tests]
    pytest

Automatic coding style checks
+++++++++++++++++++++++++++++

Enable enable automatic checks of code sanity and coding style::

    pip install -e .[pre_commit]
    pre-commit install

After this, the `yapf <https://github.com/google/yapf>`_ formatter,
the `ruff <https://docs.astral.sh/ruff/>`_ linter, and
the `mypy <http://www.mypy-lang.org/>`_ static type checker will run
at every commit.

If you ever need to skip these pre-commit hooks, just use::

    git commit -n


Continuous integration
++++++++++++++++++++++

``aiida-test-cache`` comes with a ``ci.yml`` file for continuous integration tests on every commit using GitHub Actions. It will:

#. run all tests
#. build the documentation
#. check coding style and version number

Online documentation
++++++++++++++++++++

The documentation of ``aiida-test-cache`` is continuously being built on
`ReadTheDocs <https://readthedocs.org/>`_, and the result is shown on
https://aiida-test-cache.readthedocs.org/.

If you have a ReadTheDocs account, you can also enable it on your own
fork for testing, but you will have to use a different name.

Local documentation
+++++++++++++++++++

Of course, you can also build the documentation locally::

    pip install -e .[docs]
    cd docs
    make
