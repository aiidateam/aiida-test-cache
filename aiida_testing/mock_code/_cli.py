#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implements the executable for running a mock AiiDA code.
"""

from datetime import datetime
import os
import sys
import shutil
import hashlib
import subprocess
import typing as ty
import fnmatch
from pathlib import Path

from ._env_keys import EnvKeys

SUBMIT_FILE = '_aiidasubmit.sh'


def run() -> None:
    """
    Run the mock AiiDA code. If the corresponding result exists, it is
    simply copied over to the current working directory. Otherwise,
    the code will replace the executable in the aiidasubmit file,
    launch the "real" code, and then copy the results into the data
    directory.
    """
    # Get environment variables
    log_path = Path(os.environ[EnvKeys.LOG_FILE.value])
    label = os.environ[EnvKeys.LABEL.value]
    data_dir = os.environ[EnvKeys.DATA_DIR.value]
    executable_path = os.environ[EnvKeys.EXECUTABLE_PATH.value]
    ignore_files = os.environ[EnvKeys.IGNORE_FILES.value].split(':')
    ignore_paths = os.environ[EnvKeys.IGNORE_PATHS.value].split(':')
    regenerate_data = os.environ[EnvKeys.REGENERATE_DATA.value] == 'True'
    fail_on_missing = os.environ[EnvKeys.FAIL_ON_MISSING.value] == 'True'

    def _log(msg: str) -> None:
        """Write a message to the log file."""
        with open(log_path, 'a', encoding='utf8') as log_file:
            log_file.write(f"{datetime.now()}:{label}: {msg}\n")

    _log('Init mock code')

    hash_digest = get_hash(_log).hexdigest()

    res_dir = Path(data_dir) / f"mock-{label}-{hash_digest}"

    if res_dir.exists():
        _log(f"Cache hit: {res_dir}")
        if regenerate_data:
            _log("Regenerating data")
            shutil.rmtree(res_dir)
    elif fail_on_missing:
        _log(f"ERROR: No cache hit for: {res_dir}")
        sys.exit("Missing cached data")
    else:
        _log(f"No cache hit for: {res_dir}")

    if not res_dir.exists():
        if not executable_path:
            _log("ERROR: No existing cache, and no executable specified.")
            sys.exit("No existing cache, and no executable specified.")

        _log(f"Running with executable: {executable_path}")

        subprocess.call([executable_path, *sys.argv[1:]])

        # back up results to data directory
        os.makedirs(res_dir)
        copy_files(
            src_dir=Path('.'),
            dest_dir=res_dir,
            ignore_files=ignore_files,
            ignore_paths=ignore_paths
        )

    else:
        # copy outputs from data directory to working directory
        for path in res_dir.iterdir():
            if path.is_dir():
                shutil.rmtree(path.name, ignore_errors=True)
                shutil.copytree(path, path.name)
            elif path.is_file():
                shutil.copyfile(path, path.name)
            else:
                _log(f"ERROR: Can not copy '{path.name}'.")
                sys.exit(f"Can not copy '{path.name}'.")


def get_hash(logger: ty.Callable[[str], None]) -> 'hashlib._Hash':
    """
    Get the MD5 hash for the current working directory.
    """
    md5sum = hashlib.md5()
    # Here the order needs to be consistent, thus globbing
    # with 'sorted'.
    used_paths = []
    for path in sorted(Path('.').glob('**/*')):
        if path.is_file() and not path.match('.aiida/**'):
            with open(path, 'rb') as file_obj:
                file_content_bytes = file_obj.read()
            if path.name == SUBMIT_FILE:
                file_content_bytes = strip_submit_content(file_content_bytes)
            md5sum.update(path.name.encode())
            md5sum.update(file_content_bytes)
            used_paths.append(str(path))

    logger(f"Hashed paths: {used_paths}")

    return md5sum


def strip_submit_content(aiidasubmit_content_bytes: bytes) -> bytes:
    """
    Helper function to strip content which changes between
    test runs from the aiidasubmit file.
    """
    aiidasubmit_content = aiidasubmit_content_bytes.decode()
    lines: ty.Iterable[str] = aiidasubmit_content.splitlines()
    # Strip lines containing the aiida_testing.mock_code environment variables.
    lines = (line for line in lines if 'export AIIDA_MOCK' not in line)
    # Remove abspath of the aiida-mock-code, but keep cmdline
    # arguments.
    lines = (line.split("aiida-mock-code'")[-1] for line in lines)
    return '\n'.join(lines).encode()


def copy_files(
    src_dir: Path, dest_dir: Path, ignore_files: ty.Iterable[str], ignore_paths: ty.Iterable[str]
) -> None:
    """Copy files from source to destination directory while ignoring certain files/folders.

    :param src_dir: Source directory
    :param dest_dir: Destination directory
    :param ignore_files: A list of file names (UNIX shell style patterns allowed) which are not copied to the
        destination.
    :param ignore_paths: A list of paths (UNIX shell style patterns allowed) which are not copied to the destination.
    """
    exclude_paths: ty.Set = {filepath for path in ignore_paths for filepath in src_dir.glob(path)}
    exclude_files = {path.relative_to(src_dir) for path in exclude_paths if path.is_file()}
    exclude_dirs = {path.relative_to(src_dir) for path in exclude_paths if path.is_dir()}

    # Here we rely on getting the directory name before
    # accessing its content, hence using os.walk.
    for dirpath, _, filenames in os.walk(src_dir):
        relative_dir = Path(dirpath).relative_to(src_dir)
        dirs_to_check = list(relative_dir.parents) + [relative_dir]

        if relative_dir.parts and relative_dir.parts[0] == ('.aiida'):
            continue

        if any(exclude_dir in dirs_to_check for exclude_dir in exclude_dirs):
            continue

        for filename in filenames:
            if any(fnmatch.fnmatch(filename, expr) for expr in ignore_files):
                continue

            if relative_dir / filename in exclude_files:
                continue

            os.makedirs(dest_dir / relative_dir, exist_ok=True)

            relative_file_path = relative_dir / filename
            shutil.copyfile(src_dir / relative_file_path, dest_dir / relative_file_path)
