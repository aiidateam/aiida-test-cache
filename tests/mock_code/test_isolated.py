"""Test isolated pytest runs, in subprocesses."""
import pytest

CONFTEST = """
import pytest
from aiida import orm, plugins

@pytest.fixture
def generate_diff_inputs():
    def _generate_diff_inputs():
        with open('file1.txt', 'rb') as f1_obj:
            file1 = orm.SinglefileData(file=f1_obj)
        with open('file2.txt', 'rb') as f2_obj:
            file2 = orm.SinglefileData(file=f2_obj)
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
            "parameters": plugins.DataFactory("diff")(dict={
                "ignore-case": False
            })
        }
        return inputs

    return _generate_diff_inputs
"""

PYFILE = """
from aiida.engine import run_get_node
def test_basic(mock_code_factory, generate_diff_inputs):
    mock_code = mock_code_factory('diff')
    builder = mock_code.get_builder()
    run_get_node(builder, **generate_diff_inputs())
    assert False
"""


def test_failure_no_cache(pytester: pytest.Pytester):
    """Test when no cache is found and --mock-fail-on-missing is set."""
    pytester.makeconftest(CONFTEST)
    pytester.path.joinpath("file1.txt").write_text("a")
    pytester.path.joinpath("file2.txt").write_text("b")
    pytester.makepyfile(PYFILE)
    result = pytester.runpytest_subprocess("-k", "test_basic", "--mock-fail-on-missing")
    result.stdout.re_match_lines([r".*ERROR: No cache hit for.*"])


def test_failure_no_executable(pytester: pytest.Pytester):
    """Test when no cache is found and no executable given."""
    pytester.makeconftest(CONFTEST)
    pytester.path.joinpath("file1.txt").write_text("a")
    pytester.path.joinpath("file2.txt").write_text("b")
    pytester.makepyfile(PYFILE)
    result = pytester.runpytest_subprocess("-k", "test_basic")
    result.stdout.re_match_lines([r".*ERROR: No existing cache, and no executable specified.*"])


def test_custom_hasher(pytester: pytest.Pytester):
    """Test using a custom hasher."""
    pytester.makeconftest(CONFTEST)
    pytester.path.joinpath("file1.txt").write_text("a")
    pytester.path.joinpath("file2.txt").write_text("b")
    pytester.makepyfile(
        """
        from aiida.engine import run_get_node
        from aiida_test_cache.mock_code import InputHasher
        class CustomHasher(InputHasher):
            def modify_content(self, path, content):
                if path.name == 'file1.txt':
                    self.log("Skipping file1.txt")
                    return None
                return content
        def test_basic(mock_code_factory, generate_diff_inputs):
            mock_code = mock_code_factory('diff', hasher=CustomHasher)
            builder = mock_code.get_builder()
            run_get_node(builder, **generate_diff_inputs())
            assert False
        """
    )
    result = pytester.runpytest_subprocess("-k", "test_basic")
    result.stdout.re_match_lines([r".*Skipping file1\.txt.*"])
