# -*- coding: utf-8 -*-
"""
Configuration file for pytest tests of aiida-testing.
"""
import pytest

pytest_plugins = ['aiida.manage.tests.pytest_fixtures', 'aiida_testing.mock_code',
'aiida_testing.export_cache']  # pylint: disable=invalid-name


@pytest.fixture
def generate_diff_inputs(datadir):
    """
    Generates inputs for the diff calculation.
    """
    def _generate_diff_inputs():
        from aiida.orm import SinglefileData
        from aiida.plugins import DataFactory

        with open(datadir / 'file1.txt', 'rb') as f1_obj:
            file1 = SinglefileData(file=f1_obj)
        with open(datadir / 'file2.txt', 'rb') as f2_obj:
            file2 = SinglefileData(file=f2_obj)

        inputs = {
            "file1": file1,
            "file2": file2,
            "metadata": {
                "options": {
                    "withmpi": False,
                    "resources": {
                        "num_machines": 1,
                        "num_mpiprocs_per_machine": 1
                    }
                }
            },
            "parameters": DataFactory("diff")(dict={
                "ignore-case": False
            })
        }
        return inputs

    return _generate_diff_inputs


### we need aiida fixtues with session scope, otherwise the calculations always get a differet
# hash, since computers or codes are different in test sessions.
# could also be solved with exports.
# TODO: make this available to aiida users in aiida-core or aiida-testing

@pytest.fixture(scope='session')
def temp_dir_session():
    """Get a temporary directory.
    E.g. to use as the working directory of an AiiDA computer.
    :return: The path to the directory
    :rtype: str
    """
    try:
        dirpath = tempfile.mkdtemp()
        yield dirpath
    finally:
        # after the test function has completed, remove the directory again
        shutil.rmtree(dirpath)



@pytest.fixture(scope='session')
def aiida_localhost_session(temp_dir_session):  # pylint: disable=redefined-outer-name
    """Get an AiiDA computer for localhost.
    Usage::
      def test_1(aiida_localhost):
          name = aiida_localhost.get_name()
          # proceed to set up code or use 'aiida_local_code_factory' instead
    :return: The computer node
    :rtype: :py:class:`aiida.orm.Computer`
    """
    from aiida.orm import Computer
    from aiida.common.exceptions import NotExistent

    name = 'localhost-test'

    try:
        computer = Computer.objects.get(name=name)
    except NotExistent:
        computer = Computer(
            name=name,
            description='localhost computer set up by test manager',
            hostname=name,
            workdir=temp_dir_session,
            transport_type='local',
            scheduler_type='direct'
        )
        computer.store()
        computer.set_minimum_job_poll_interval(0.)
        computer.set_default_mpiprocs_per_machine(1)
        computer.configure()

    return computer



@pytest.fixture(scope='session')
def aiida_local_code_factory_session(aiida_localhost_session):  # pylint:disable=redefined-outer-name
    """
    Get an AiiDA code on localhost.
    Searches in the PATH for a given executable and creates an AiiDA code with provided entry
point.
    Usage::
      def test_1(aiida_local_code_factory):
          code = aiida_local_code_factory('pw.x', 'quantumespresso.pw')
          # use code for testing ...
    :return: A function get_code(executable, entry_point) that returns the Code node.
    :rtype: object
    """

    def get_code(entry_point, executable, computer=aiida_localhost_session, prepend_text=None):
        """Get local code.
        Sets up code for given entry point on given computer.
        :param entry_point: Entry point of calculation plugin
        :param executable: name of executable; will be searched for in local system PATH.
        :param computer: (local) AiiDA computer
        :return: The code node
        :rtype: :py:class:`aiida.orm.Code`
        """
        from aiida.orm import Code

        codes = Code.objects.find(filters={'label': executable})  # pylint: disable=no-member
        if codes:
            return codes[0]

        executable_path = shutil.which(executable)

        if not executable_path:
            raise ValueError('The executable "{}" was not found in the $PATH.'.format(executable))

        code = Code(
            input_plugin_name=entry_point,
            remote_computer_exec=[computer, executable_path]
        )
        code.label = executable
        if prepend_text is not None:
            code.set_prepend_text(prepend_text)
        return code.store()

    return get_code



@pytest.fixture(scope='session')
def reuse_local_code(aiida_local_code_factory_session):

    def _get_code(executable, exec_relpath, entrypoint, prepend_text=None):
        import os, pathlib
        from aiida.tools.importexport import import_data, export
        from aiida.orm import ProcessNode, QueryBuilder, Code, load_node

        cwd = pathlib.Path(os.getcwd())                  # Might be not the best idea.
        data_dir = (cwd / 'data_dir')                    # TODO: get from config?
        full_import_path = str(data_dir)+'/'+executable+'.tar.gz'
        # check if exported code exists and load it, otherwise create new code (will have different
        # has due to different working directory)
        if pathlib.Path(full_import_path).exists():
            import_data(full_import_path)
            codes = Code.objects.find(filters={'label': executable})  # pylint: disable=no-member
            code = codes[0]
            code.computer.configure()

        else:
            # make sure code is found in PATH
            _exe_path = os.path.abspath(exec_relpath)
            os.environ['PATH']+=':'+_exe_path
            # get code using aiida_local_code_factory fixture
            code = aiida_local_code_factory_session(entrypoint, executable, prepend_text=prepend_text)

            #export for later reuse
            export([code], outfile=full_import_path, overwrite=True) # add export of extras automatically

        return code

    return _get_code

