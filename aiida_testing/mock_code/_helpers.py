#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implements the executable for running a mock AiiDA code.
"""

import os
import shutil
import pathlib
import hashlib
import typing as ty
import fnmatch
from pathlib import Path

from aiida import orm

SUBMIT_FILE = '_aiidasubmit.sh'


def get_hash(dirpath: pathlib.Path, code: orm.Code) -> 'hashlib._Hash':
    """
    Get the MD5 hash for the current working directory.
    """
    md5sum = hashlib.md5()
    # Here the order needs to be consistent, thus globbing
    # with 'sorted'.
    for path in sorted(dirpath.glob('**/*')):
        if path.is_file() and not path.match('.aiida/**'):
            with open(path, 'rb') as file_obj:
                file_content_bytes = file_obj.read()
            if path.name == SUBMIT_FILE:
                file_content_bytes = strip_submit_content(file_content_bytes, code=code)
            md5sum.update(path.name.encode())
            md5sum.update(file_content_bytes)

    return md5sum


def strip_submit_content(aiidasubmit_content_bytes: bytes, code: orm.Code) -> bytes:
    """
    Helper function to strip content which changes between
    test runs from the aiidasubmit file.
    """
    aiidasubmit_content = aiidasubmit_content_bytes.decode()
    replaced_content = aiidasubmit_content.replace(f"'{code.get_remote_exec_path()}'", '')
    # code.label)
    return replaced_content.encode()


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
