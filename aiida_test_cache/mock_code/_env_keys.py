"""
Defines the environment variable names for the mock code execution.
"""
import inspect
import os
import typing as ty
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ._hasher import InputHasher, load_hasher


@dataclass
class MockVariables:
    """
    A class containing variables defined for the mock code execution.
    """

    log_file: Path
    label: str
    test_name: str
    data_dir: Path
    executable_path: str
    ignore_paths: ty.Iterable[str]
    regenerate_data: bool
    fail_on_missing: bool
    _hasher: ty.Union[str, type[InputHasher]]

    @classmethod
    def from_env(cls) -> "MockVariables":
        """
        Create a MockVariables instance from the environment variables.
        """
        return cls(
            log_file=Path(os.environ[_EnvKeys.LOG_FILE.value]),
            label=os.environ[_EnvKeys.LABEL.value],
            test_name=os.environ[_EnvKeys.TEST_NAME.value],
            data_dir=Path(os.environ[_EnvKeys.DATA_DIR.value]),
            executable_path=os.environ[_EnvKeys.EXECUTABLE_PATH.value],
            ignore_paths=os.environ[_EnvKeys.IGNORE_PATHS.value].split(":"),
            regenerate_data=os.environ[_EnvKeys.REGENERATE_DATA.value] == "True",
            fail_on_missing=os.environ[_EnvKeys.FAIL_ON_MISSING.value] == "True",
            _hasher=os.environ.get(_EnvKeys.HASHER.value, InputHasher),
        )

    def get_hasher(self) -> type[InputHasher]:
        """
        Return the hasher class.
        """
        if isinstance(self._hasher, str):
            # split the string into the file path and the class name
            file_path, class_name = self._hasher.rsplit("::", 1)
            return load_hasher(file_path, class_name)
        return self._hasher

    def to_env(self) -> str:
        """
        Return a string that can be used to export the environmental variables
        """
        string = inspect.cleandoc(
            f"""
                export {_EnvKeys.LOG_FILE.value}="{self.log_file}"
                export {_EnvKeys.TEST_NAME.value}="{self.test_name.replace('"', "_")}"
                export {_EnvKeys.LABEL.value}="{self.label}"
                export {_EnvKeys.DATA_DIR.value}="{self.data_dir}"
                export {_EnvKeys.EXECUTABLE_PATH.value}="{self.executable_path}"
                export {_EnvKeys.IGNORE_PATHS.value}="{':'.join(self.ignore_paths)}"
                export {_EnvKeys.REGENERATE_DATA.value}={'True' if self.regenerate_data else 'False'}
                export {_EnvKeys.FAIL_ON_MISSING.value}={'True' if self.fail_on_missing else 'False'}
                """
        )
        if self._hasher is not InputHasher:
            if isinstance(self._hasher, str):
                value = self._hasher
            else:
                value = f"{os.path.abspath(inspect.getfile(self._hasher))}::{self._hasher.__name__}"
            string += f'\nexport {_EnvKeys.HASHER.value}="{value}"'
        return string


class _EnvKeys(Enum):
    """
    An enum containing the environment variables defined for
    the mock code execution.
    """

    LOG_FILE = "AIIDA_MOCK_LOG_FILE"
    TEST_NAME = "AIIDA_MOCK_TEST_NAME"
    LABEL = "AIIDA_MOCK_LABEL"
    DATA_DIR = "AIIDA_MOCK_DATA_DIR"
    EXECUTABLE_PATH = "AIIDA_MOCK_EXECUTABLE_PATH"
    IGNORE_PATHS = "AIIDA_MOCK_IGNORE_PATHS"
    REGENERATE_DATA = "AIIDA_MOCK_REGENERATE_DATA"
    FAIL_ON_MISSING = "AIIDA_MOCK_FAIL_ON_MISSING"
    HASHER = "AIIDA_MOCK_HASHER"
