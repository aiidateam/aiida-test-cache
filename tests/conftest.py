"""
Configuration file for pytest tests of aiida-test-cache.
"""
import pytest
from aiida import __version__ as aiida_version
from packaging.version import Version

pytest_plugins = [
    'pytester',
]

# Compatibility with old aiida-core fixtures
if Version(aiida_version) < Version('2.7.0'):

    @pytest.fixture
    def aiida_profile_clean(clear_database):
        pass

    @pytest.fixture
    def aiida_code_installed(aiida_local_code_factory):

        def _code(filepath_executable, default_calc_job_plugin):
            return aiida_local_code_factory(
                executable=filepath_executable, entry_point=default_calc_job_plugin
            )

        return _code


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
