"""Hashing of input files."""
import hashlib
import inspect
import typing as ty
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

if ty.TYPE_CHECKING:
    from ._env_keys import MockVariables


class InputHasher:
    """
    Helper class to hash the input contents for the mock code.
    """
    SUBMIT_FILE = '_aiidasubmit.sh'

    def __init__(self, variables: 'MockVariables', logger: ty.Callable[[str], None]) -> None:
        """Initialize the hasher."""
        self.log = logger
        self.variables = variables

    def __call__(self, cwd: Path) -> str:
        """Generate the MD5 hash for the directory."""
        md5sum = hashlib.md5()
        # Here the order needs to be consistent, thus globbing
        # with 'sorted'.
        used_paths = []
        file_content_bytes: ty.Optional[bytes]
        for path in sorted(cwd.glob('**/*')):
            if not path.is_file() or path.match('.aiida/**'):
                continue
            with open(path, 'rb') as file_obj:
                file_content_bytes = file_obj.read()
            if path.name == self.SUBMIT_FILE:
                file_content_bytes = self._strip_submit_content(file_content_bytes)
                # TODO: This is a temporary ugly hack for backward compatibility with aiida-core<2.3
                # REVERT THIS after 0.0.1 release!
                if not file_content_bytes.endswith(b" "):
                    file_content_bytes += b" "
            file_content_bytes = self.modify_content(path, file_content_bytes)
            if file_content_bytes is not None:
                md5sum.update(path.name.encode())
                md5sum.update(file_content_bytes)
                used_paths.append(str(path))

        self.log(f"Hashed paths: {used_paths}")

        return md5sum.hexdigest()

    def modify_content(self, path: Path, content: bytes) -> ty.Optional[bytes]:  # noqa: ARG002
        """A sub-class hook to modify the contents of the file, before hashing.

        If None is returned, the file is ignored, when generating the hash.
        """
        return content

    @staticmethod
    def _strip_submit_content(content: bytes) -> bytes:
        """
        Helper function to strip content which changes between
        test runs from the aiidasubmit file.
        """
        aiidasubmit_content = content.decode()
        lines: ty.Iterable[str] = aiidasubmit_content.splitlines()
        # Strip lines containing the aiida_test_cache.mock_code environment variables.
        lines = (line for line in lines if 'export AIIDA_MOCK' not in line)
        # Remove abspath of the aiida-mock-code, but keep cmdline arguments.
        lines = (line.split("aiida-mock-code'")[-1] for line in lines)
        return '\n'.join(lines).encode()


def load_hasher(path: ty.Union[str, Path], class_name: str) -> type[InputHasher]:
    """
    Load the InputHasher class from the given path.
    """
    spec = spec_from_file_location("_aiida_mock_hasher", path)
    if not spec or not spec.loader:
        raise ImportError(f"Could not import {path}")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    hasher = getattr(mod, class_name)
    if not inspect.isclass(hasher):
        raise TypeError(f"Object {class_name!r} is not a class.")
    if not issubclass(hasher, InputHasher):
        raise TypeError(f"Class {class_name!r} is not a subclass of {InputHasher.__name__}")
    return hasher
