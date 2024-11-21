"""
Configuration file for pytest tests of aiida-test-cache.
"""
import pytest

pytest_plugins = [
    'pytester',
]


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
