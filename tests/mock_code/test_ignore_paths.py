# -*- coding: utf-8 -*-
"""
Test that ignoring paths works as expected.
"""
import os
from pathlib import Path
import pytest

from aiida_testing.mock_code._cli import copy_files

OUTPUT_PATHS = (
    Path('file1.txt'),
    Path('file2.txt'),
    Path('_aiidasubmit.sh'),
    Path('my/subfolder/file3.txt'),
    Path('my/subfolder/file4.txt'),
)


@pytest.fixture
def run_directory(tmp_path_factory):
    """
    Prepare mock directory structure for run directory of code.
    """
    tmp_path = tmp_path_factory.mktemp('output')
    for path in OUTPUT_PATHS:
        if os.path.dirname(path):
            os.makedirs(tmp_path / os.path.dirname(path), exist_ok=True)
        with open(tmp_path / path, 'w', encoding='utf8') as handle:
            handle.write("Test content")

    yield tmp_path


def test_ignore_paths(run_directory, tmp_path_factory):  # pylint: disable=redefined-outer-name
    """Test that ignore_paths works as expected."""
    storage_directory = tmp_path_factory.mktemp('storage')

    # ignore everything
    copy_files(
        src_dir=run_directory, dest_dir=storage_directory, ignore_files=(), ignore_paths=('*', )
    )
    assert not (storage_directory / '_aiidasubmit.sh').is_file()

    # ignore subfolder
    copy_files(
        src_dir=run_directory, dest_dir=storage_directory, ignore_files=(), ignore_paths=('my/', )
    )
    copy_files(
        src_dir=run_directory,
        dest_dir=storage_directory,
        ignore_files=(),
        ignore_paths=('my/subfolder', )
    )
    assert (storage_directory / '_aiidasubmit.sh').is_file()
    assert (storage_directory / 'file2.txt').is_file()
    assert not (storage_directory / 'my' / 'subfolder' / 'file3.txt').is_file()

    # ignore only specific file (from subfolder)
    copy_files(
        src_dir=run_directory,
        dest_dir=storage_directory,
        ignore_files=(),
        ignore_paths=('my/subfolder/file3.txt', )
    )
    assert not (storage_directory / 'my' / 'subfolder' / 'file3.txt').is_file()

    # all should be there
    copy_files(src_dir=run_directory, dest_dir=storage_directory, ignore_files=(), ignore_paths=())
    assert (storage_directory / 'my' / 'subfolder' / 'file3.txt').is_file()


def test_ignore_files(run_directory, tmp_path_factory):  # pylint: disable=redefined-outer-name
    """Test that ignore_files works as expected."""
    storage_directory = tmp_path_factory.mktemp('storage')

    # ignore everything
    copy_files(
        src_dir=run_directory, dest_dir=storage_directory, ignore_files=('*'), ignore_paths=()
    )
    assert not (storage_directory / '_aiidasubmit.sh').is_file()
    assert not (storage_directory / 'my' / 'subfolder' / 'file3.txt').is_file()

    # ignore only specific file (from subfolder)
    copy_files(
        src_dir=run_directory,
        dest_dir=storage_directory,
        ignore_files=('file3.txt', ),
        ignore_paths=()
    )
    assert not (storage_directory / 'my' / 'subfolder' / 'file3.txt').is_file()
    assert (storage_directory / 'file2.txt').is_file()

    # all should be there
    copy_files(src_dir=run_directory, dest_dir=storage_directory, ignore_files=(), ignore_paths=())
    assert (storage_directory / 'my' / 'subfolder' / 'file3.txt').is_file()
