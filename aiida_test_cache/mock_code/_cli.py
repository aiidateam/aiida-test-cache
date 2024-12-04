#!/usr/bin/env python
"""
Implements the executable for running a mock AiiDA code.
"""
import os
import shutil
import subprocess
import sys
import typing as ty
from datetime import datetime
from pathlib import Path

from ._env_keys import MockVariables


def run() -> None:
    """
    Run the mock AiiDA code. If the corresponding result exists, it is
    simply copied over to the current working directory. Otherwise,
    the code will replace the executable in the aiidasubmit file,
    launch the "real" code, and then copy the results into the data
    directory.
    """
    # Get environment variables
    env = MockVariables.from_env()

    def _log(msg: str, error=False) -> None:
        """Write a message to the log file."""
        if error:
            msg = f"ERROR: {msg}"
        with open(env.log_file, 'a', encoding='utf8') as log_file:
            log_file.write(f"{datetime.now()}:{env.label}: {msg}\n")
        if error:
            sys.exit(msg)

    _log('Init mock code')

    try:
        hasher_cls = env.get_hasher()
    except Exception as exc:
        _log(f"loading hasher: {exc}", error=True)

    try:
        hash_digest = hasher_cls(env, _log)(Path('.'))
    except Exception as exc:
        _log(f"computing hash: {exc}", error=True)

    res_dir = env.data_dir / f"mock-{env.label}-{hash_digest}"

    if res_dir.exists():
        _log(f"Cache hit: {res_dir}")
        if env.regenerate_data:
            _log("Regenerating data")
            shutil.rmtree(res_dir)
    elif env.fail_on_missing:
        _log(f"No cache hit for: {res_dir}", error=True)
    else:
        _log(f"No cache hit for: {res_dir}")

    if not res_dir.exists():
        if not env.executable_path:
            _log("No existing cache, and no executable specified.", error=True)

        _log(f"Running with executable: {env.executable_path}")

        subprocess.call([env.executable_path, *sys.argv[1:]])

        # back up results to data directory
        os.makedirs(res_dir)
        copy_files(src_dir=Path('.'), dest_dir=res_dir, ignore_paths=env.ignore_paths)

    else:
        # copy outputs from data directory to working directory
        for path in res_dir.iterdir():
            if path.is_dir():
                shutil.rmtree(path.name, ignore_errors=True)
                shutil.copytree(path, path.name)
            elif path.is_file():
                shutil.copyfile(path, path.name)
            else:
                _log(f"Can not copy '{path.name}'.", error=True)


def copy_files(src_dir: Path, dest_dir: Path, ignore_paths: ty.Iterable[str]) -> None:
    """Copy files from source to destination directory while ignoring certain files/folders.

    :param src_dir: Source directory
    :param dest_dir: Destination directory
    :param ignore_paths: A list of paths (UNIX shell style patterns allowed) which are not copied to the destination.
    """
    exclude_paths: set = {filepath for path in ignore_paths for filepath in src_dir.glob(path)}
    exclude_files = {path.relative_to(src_dir) for path in exclude_paths if path.is_file()}
    exclude_dirs = {path.relative_to(src_dir) for path in exclude_paths if path.is_dir()}

    # Here we rely on getting the directory name before
    # accessing its content, hence using os.walk.
    for dirpath, _, filenames in os.walk(src_dir):
        relative_dir = Path(dirpath).relative_to(src_dir)
        dirs_to_check = [*list(relative_dir.parents), relative_dir]

        if relative_dir.parts and relative_dir.parts[0] == ('.aiida'):
            continue

        if any(exclude_dir in dirs_to_check for exclude_dir in exclude_dirs):
            continue

        for filename in filenames:

            if relative_dir / filename in exclude_files:
                continue

            os.makedirs(dest_dir / relative_dir, exist_ok=True)

            relative_file_path = relative_dir / filename
            shutil.copyfile(src_dir / relative_file_path, dest_dir / relative_file_path)
