"""
Defines a pytest fixture for creating mock AiiDA codes.
"""

import collections
import os
import pathlib
import shutil
import typing as ty
import uuid

import click
import pytest
from aiida.orm import Code

from .._config import CONFIG_FILE_NAME, Config, ConfigActions
from ._env_keys import MockVariables
from ._hasher import InputHasher

__all__ = (
    "mock_code_factory",
    "mock_disable_mpi",
    "mock_fail_on_missing",
    "mock_regenerate_test_data",
    "pytest_addoption",
    "testing_config",
    "testing_config_action",
)


def pytest_addoption(parser):
    """Add pytest command line options."""
    parser.addoption(
        "--testing-config-action",
        type=click.Choice([c.value for c in ConfigActions]),
        default=ConfigActions.READ.value,
        help=f"Read {CONFIG_FILE_NAME} config file if present ('read'), require config file ('require') or " \
             "generate new config file ('generate').",
    )
    parser.addoption(
        "--mock-regenerate-test-data",
        action="store_true",
        default=False,
        help="Regenerate test data."
    )
    parser.addoption(
        "--mock-fail-on-missing",
        action="store_true",
        default=False,
        help="Fail if cached data is not found, rather than regenerating it.",
    )
    parser.addoption(
        "--mock-disable-mpi",
        action="store_true",
        default=False,
        help="Run all calculations with `metadata.options.usempi=False`.",
    )


@pytest.fixture(scope='session')
def testing_config_action(request):
    """Read action for testing configuration from command line option."""
    return request.config.getoption("--testing-config-action")


@pytest.fixture(scope='session')
def mock_regenerate_test_data(request):
    """Read whether to regenerate test data from command line option."""
    return request.config.getoption("--mock-regenerate-test-data")


@pytest.fixture(scope='session')
def mock_fail_on_missing(request):
    """Read whether to fail if cached data is not found, rather than regenerating it."""
    return request.config.getoption("--mock-fail-on-missing")


@pytest.fixture(scope='function')
def mock_disable_mpi(request):
    """Enforce `withmpi=False` based on `--mock-disable-mpi` cli option.

    This is achieved by monkey-patching the `CalcJob.get_option()` method.
    """
    return request.config.getoption("--mock-disable-mpi")


@pytest.fixture(scope='session')
def testing_config(testing_config_action):
    """Get content of .aiida-test-cache-config.yml

    testing_config_action :
        Read config file if present ('read'), require config file ('require') or generate new config file ('generate').
    """
    config = Config.from_file()

    if not config and testing_config_action == ConfigActions.REQUIRE.value:
        raise ValueError(f"Unable to find {CONFIG_FILE_NAME}.")

    yield config

    if testing_config_action == ConfigActions.GENERATE.value:
        config.to_file()


def _forget_mpi_decorator(func):
    """Modify :py:meth:`aiida.orm.Code.get_prepend_cmdline_params` to discard MPI parameters."""

    def _get_prepend_cmdline_params(self, mpi_args=None, extra_mpirun_params=None):  # noqa: ARG001
        return func(self)

    return _get_prepend_cmdline_params


@pytest.fixture(scope='function')
def mock_code_factory(
    aiida_localhost, testing_config, testing_config_action, mock_regenerate_test_data,
    mock_fail_on_missing, mock_disable_mpi, monkeypatch, request, tmp_path
):
    """
    Fixture to create a mock AiiDA Code.

    testing_config_action :
        Read config file if present ('read'), require config file ('require') or generate new config file ('generate').

    """
    log_file = tmp_path.joinpath("_aiida_mock_code.log")
    log_file.touch()

    def _get_mock_code(
        label: str,
        entry_point: ty.Optional[str] = None,
        data_dir_abspath: ty.Union[None, str, pathlib.Path] = None,
        ignore_paths: ty.Iterable[str] = ('_aiidasubmit.sh', ),
        executable_name: str = '',
        hasher: type[InputHasher] = InputHasher,
        _config: Config = testing_config,
        _config_action: str = testing_config_action,
        _regenerate_test_data: bool = mock_regenerate_test_data,
        _fail_on_missing: bool = mock_fail_on_missing,
        _disable_mpi: bool = mock_disable_mpi,
    ):
        """
        Creates a mock AiiDA code. If the same inputs have been run previously,
        the results are copied over from the corresponding sub-directory of
        the ``data_dir_abspath``. Otherwise, the code is executed.

        Parameters
        ----------
        label :
            Label by which the code is identified in the configuration file.
        entry_point :
            The AiiDA calculation entry point for the default calculation
            of the code.
        data_dir_abspath :
            Absolute path of the directory where the code results are
            stored.
        ignore_paths :
            A list of paths (UNIX shell style patterns allowed) that are not copied to the results directory
            after the code has been executed.
        executable_name :
            Name of code executable to search for in PATH, if configuration file does not specify location already.
        _config :
            Dict with contents of configuration file
        _config_action :
            If 'require', raise ValueError if config dictionary does not specify path of executable.
            If 'generate', add new key (label) to config dictionary.
        _regenerate_test_data :
            If True, regenerate test data instead of reusing.
        """
        # It's easy to forget the final comma and pass a string, e.g. `ignore_paths = ('_aiidasubmit.sh')`
        assert isinstance(ignore_paths, collections.abc.Iterable) and not isinstance(ignore_paths, str), \
                f"'ignore_paths' argument must be tuple or list, found {type(ignore_paths)}"

        if entry_point is None:
            entry_point = label
        if data_dir_abspath is None:
            request.node.path.parent.joinpath("data").mkdir(exist_ok=True)
            data_dir_abspath = request.node.path.parent / "data"
        assert issubclass(
            hasher, InputHasher
        ), f"hasher must be a subclass of {InputHasher.__name__}"

        # we want to set a custom prepend_text, which is why the code
        # can not be reused.
        code_label = f'mock-{label}-{uuid.uuid4()}'

        data_dir_pl = pathlib.Path(data_dir_abspath)
        if not data_dir_pl.exists():
            raise ValueError(f"Data directory '{data_dir_abspath}' does not exist")
        if not data_dir_pl.is_absolute():
            raise ValueError("Please provide absolute path to data directory.")

        mock_executable_path = shutil.which('aiida-mock-code')
        if not mock_executable_path:
            raise ValueError(
                "'aiida-mock-code' executable not found in the PATH. " +
                "Have you run `pip install aiida-test-cache` in this python environment?"
            )

        # try determine path to actual code executable
        mock_code_config = _config.get('mock_code', {})
        if _config_action == ConfigActions.REQUIRE.value and label not in mock_code_config:
            raise ValueError(
                f"Configuration file {CONFIG_FILE_NAME} does not specify path to executable for code label '{label}'."
            )

        code_executable_path = mock_code_config.get(label, '')
        if label in mock_code_config and not pathlib.Path(mock_code_config[label]).is_absolute():
            # Relative paths are interpreted with respect to the
            # .aiida-testing-config.yml file
            relative_path = _config.file_path.parent / mock_code_config[label]
            code_executable_path = os.fspath(relative_path)
            if not relative_path.exists():
                raise ValueError(
                    f"Relative path {code_executable_path} in {CONFIG_FILE_NAME} "
                    f"does not exist for code label '{label}'."
                )
        elif label not in mock_code_config and executable_name:
            _exec_path = shutil.which(executable_name)
            if _exec_path is None:
                raise ValueError(
                    f"Executable {executable_name} not found on PATH for code label '{label}'."
                )
            code_executable_path = _exec_path

        if _config_action == ConfigActions.GENERATE.value:
            mock_code_config[label] = code_executable_path
        code = Code(
            input_plugin_name=entry_point,
            remote_computer_exec=[aiida_localhost, mock_executable_path]
        )
        code.label = code_label
        variables = MockVariables(
            log_file=log_file.absolute(),
            label=label,
            test_name=request.node.name,
            data_dir=data_dir_pl,
            executable_path=code_executable_path,
            ignore_paths=ignore_paths,
            regenerate_data=_regenerate_test_data,
            fail_on_missing=_fail_on_missing,
            _hasher=hasher,
        )
        code.set_prepend_text(variables.to_env())

        code.store()

        # Monkeypatch MPI behavior of code class, if requested either directly via `--mock-disable-mpi` or
        # indirectly via `--mock-fail-on-missing` (no need to use MPI in this case)
        if _disable_mpi or _fail_on_missing:
            monkeypatch.setattr(
                code.__class__, 'get_prepend_cmdline_params',
                _forget_mpi_decorator(code.__class__.get_prepend_cmdline_params)
            )

        return code

    yield _get_mock_code

    log_text = log_file.read_text("utf8")
    print("AiiDA mock code logging:")
    if log_text:
        print(log_text)
