"""
Defines pytest fixtures for automatically enable caching in tests and create aiida archives if not existent.
Meant to be useful for WorkChain tests.
"""
import os
import pathlib
import shutil
import typing as ty
from contextlib import contextmanager

import pytest
from aiida import plugins
from aiida.common.links import LinkType
from aiida.manage.caching import enable_caching
from aiida.orm import (
    CalcJobNode,
    Code,
    Dict,
    FolderData,
    List,
    QueryBuilder,
    RemoteData,
    SinglefileData,
    StructureData,
)

from .._config import Config
from ._utils import (
    create_node_archive,
    get_node_from_hash_objects_caller,
    load_node_archive,
    monkeypatch_hash_objects,
)

__all__ = (
    "absolute_archive_path", "archive_cache_forbid_migration", "archive_cache_overwrite",
    "enable_archive_cache", "liberal_hash", "pytest_addoption"
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add pytest command line options."""
    parser.addoption(
        "--archive-cache-forbid-migration",
        action="store_true",
        default=False,
        help="If True the stored archives cannot be migrated if their versions are incompatible."
    )
    parser.addoption(
        "--archive-cache-overwrite",
        action="store_true",
        default=False,
        help=
        "If True the stored archives are overwritten with the archive created by the current test run."
    )


@pytest.fixture(scope='session')
def archive_cache_forbid_migration(request: pytest.FixtureRequest) -> bool:
    """Read whether aiida is forbidden from migrating the test archives if their versions are incompatible."""
    return request.config.getoption( #type:ignore [no-any-return]
        "--archive-cache-forbid-migration"
    )


@pytest.fixture(scope='session')
def archive_cache_overwrite(request: pytest.FixtureRequest) -> bool:
    """Read whether the test archives should be overwritten in this test run."""
    return request.config.getoption(  #type:ignore [no-any-return]
        "--archive-cache-overwrite"
    )


@pytest.fixture(scope='function')
def absolute_archive_path(
    request: pytest.FixtureRequest, testing_config: Config, archive_cache_forbid_migration: bool,
    tmp_path_factory: pytest.TempPathFactory
) -> ty.Callable:
    """
    Fixture to get the absolute filepath for a given archive

    1. An absolute file path is not modified
    2. If the given path is relative the absolute path is constructed with respect to
        either
        - the `default_data_dir` specified in the `archive_cache` section of the config file
        - if no such option is specified a directory `caches` is used in the folder of the current test file
    """

    archive_cache_config = testing_config.get('archive_cache', {})

    def _absolute_archive_path(
        archive_path: ty.Union[str, pathlib.Path], overwrite: bool = False
    ) -> str:
        """
        Returns the absolute filepath to the given archive according to the
        specified configuration

        1. An absolute file path is not modified
        2. If the given path is relative the absolute path is constructed with respect to
           either
           - the `default_data_dir` specified in the `archive_cache` section of the config file
           - if no such option is specified a directory `caches` is used in the folder of the current test file

        :param archive_path: path to the AiiDA archive (will be used according to the rules above)

        .. note::

            If the archive at the determined absolute path exists, is allowed to be migrated
            , i.e. the `--archive-cache-forbid-migration` options is not specified,
            and overwrite is False (either argument or `--archive-cache-overwrite` cmdline option),
            the archive will be copied into a temporary directory created by pytest

            This prevents unwanted test file changes, when testing AiiDA versions not matching the
            archive versions of the caches

        """
        default_data_dir = archive_cache_config.get('default_data_dir', '')
        archive_path = pathlib.Path(archive_path)

        if archive_path.is_absolute():
            full_archive_path = archive_path
        else:
            if not default_data_dir:
                #Path relative to the test file defining the current test
                default_data_dir = request.path.parent / 'caches'
            else:
                default_data_dir = pathlib.Path(default_data_dir)
            if not default_data_dir.exists():
                try:
                    default_data_dir.mkdir()
                except OSError as exc:
                    raise ValueError(
                        f'Could not create the `{default_data_dir}` archive directory'
                        'Please make sure that all parent directories exist'
                    ) from exc

            full_archive_path = pathlib.Path(default_data_dir) / archive_path

        #Create a copy in a temporary directory of the archive if migration is allowed
        #Migrating the archive would otherwise modify the test file, which
        #is most likely not desired
        #If the archive is supposed to be overwritten it needs to be the actual path
        if full_archive_path.exists() and \
            not archive_cache_forbid_migration and \
            not overwrite:
            test_file_name = pathlib.Path(request.module.__file__).name
            data_dir = tmp_path_factory.mktemp(test_file_name)
            shutil.copy(os.fspath(full_archive_path), os.fspath(data_dir))
            full_archive_path = data_dir / full_archive_path.name

        return os.fspath(full_archive_path.absolute())

    return _absolute_archive_path


@pytest.fixture(scope='function')
def enable_archive_cache(
    liberal_hash: None,  # noqa: ARG001
    archive_cache_forbid_migration: bool,
    archive_cache_overwrite: bool,
    absolute_archive_path: ty.Callable
) -> ty.Callable:
    """
    Fixture to use in a with block
    - Before the block the given cache is loaded (if it exists)
    - within this block the caching of AiiDA is enabled.
    - At the end an AiiDA export can be created (if test data should be overwritten)
    Requires an absolute path to the export file to load or export to.
    Export the provenance of all calcjobs nodes within the test.
    """

    @contextmanager
    def _enable_archive_cache(
        archive_path: ty.Union[str, pathlib.Path],
        calculation_class: ty.Union[type[CalcJobNode], ty.Sequence[type[CalcJobNode]], None] = None,
        overwrite: bool = False
    ) -> ty.Generator[None, None, None]:
        """
        Contextmanager to run calculation within, which aiida graph gets exported

        :param archive_path: Path to the AiiDA archive to load/create
        :param calculation_class: limit what kind of Calcjobs are considered in the archive
                                  either a single class or a tuple of classes to cache and archive
        :param overwrite: bool, if True any existing archive is overwritten at the end of
                          the with block
        """
        overwrite = overwrite or archive_cache_overwrite

        full_archive_path = absolute_archive_path(archive_path, overwrite=overwrite)
        # check and load export
        export_exists = os.path.isfile(full_archive_path)
        if export_exists:
            load_node_archive(full_archive_path, forbid_migration=archive_cache_forbid_migration)

        # default enable globally for all jobcalcs
        identifier = None
        if calculation_class is not None:
            if isinstance(calculation_class, (tuple, list)):
                identifier = ':'.join(c.build_process_type() for c in calculation_class)
            else:
                identifier = calculation_class.build_process_type()  #type: ignore[union-attr]

        with enable_caching(identifier=identifier):
            yield  # now the test runs

        # This is executed after the test
        if not export_exists or overwrite:
            # in case of yield: is the db already cleaned?
            # create export of all calculation_classes
            # Another solution out of this is to check the time before and
            # after the yield and export ONLY the jobcalc classes created within this time frame
            queryclass: ty.Union[type[CalcJobNode], ty.Sequence[type[CalcJobNode]]]
            if calculation_class is None:
                queryclass = CalcJobNode
            else:
                queryclass = calculation_class
            qub = QueryBuilder()
            qub.append(queryclass, tag='node')  # query for CalcJobs nodes
            to_export = [entry[0] for entry in qub.all()]
            create_node_archive(
                nodes=to_export, archive_path=full_archive_path, overwrite=overwrite
            )

    return _enable_archive_cache


@pytest.fixture
def liberal_hash(monkeypatch: pytest.MonkeyPatch, testing_config: Config) -> None:
    """
    Monkeypatch .get_objects_to_hash of Code, CalcJobNodes and core Data nodes of aiida-core
    to not include the uuid of the computer and less information of the code node in the hash
    and remove aiida-core version from hash
    """
    hash_ignore_config = testing_config.get('archive_cache', {}).get('ignore', {})

    #Load the corresponding entry points
    node_ignored_attributes = {
        plugins.DataFactory(entry_point): (*tuple(set(ignored)), "version")
        for entry_point, ignored in hash_ignore_config.get('node_attributes', {}).items()
    }
    calcjob_ignored_attributes = (
        *tuple(hash_ignore_config.get("calcjob_attributes", [])), "version"
    )
    calcjob_ignored_inputs = tuple(hash_ignore_config.get('calcjob_inputs', []))

    def mock_objects_to_hash_code(self):
        """
        Return a list of objects which should be included in the hash of a Code node
        """
        self = get_node_from_hash_objects_caller(self)
        # computer names are changed by aiida-core if imported and do not have same uuid.
        return [self.base.attributes.get(key='input_plugin')]

    def mock_objects_to_hash_calcjob(self):
        """
        Return a list of objects which should be included in the hash of a CalcJobNode.
        code from aiida-core, only self.computer.uuid is commented out
        """
        hash_ignored_inputs = self._hash_ignored_inputs
        self = get_node_from_hash_objects_caller(self)

        hash_ignored_inputs = tuple(hash_ignored_inputs) + calcjob_ignored_inputs
        self._hash_ignored_attributes = tuple(self._hash_ignored_attributes) + \
                                        calcjob_ignored_attributes

        objects = [{
            key: val
            for key, val in self.base.attributes.items()
            if key not in self._hash_ignored_attributes and key not in self._updatable_attributes
        },
                   {
                       entry.link_label: entry.node.base.caching.get_hash()
                       for entry in self.base.links.get_incoming(
                           link_type=(LinkType.INPUT_CALC, LinkType.INPUT_WORK)
                       ) if entry.link_label not in hash_ignored_inputs
                   }]
        return objects

    def mock_objects_to_hash(self):
        """
        Return a list of objects which should be included in the hash of all Nodes.
        """
        self = get_node_from_hash_objects_caller(self)
        class_name = self.__class__.__name__

        self._hash_ignored_attributes = tuple(self._hash_ignored_attributes) + \
                                        node_ignored_attributes.get(class_name, ('version',))

        objects = [
            {
                key: val
                for key, val in self.base.attributes.items() if
                key not in self._hash_ignored_attributes and key not in self._updatable_attributes
            },
        ]
        return objects

    monkeypatch_hash_objects(monkeypatch, Code, mock_objects_to_hash_code)
    monkeypatch_hash_objects(monkeypatch, CalcJobNode, mock_objects_to_hash_calcjob)

    nodes_to_patch = [Dict, SinglefileData, List, FolderData, RemoteData, StructureData]
    for node_class in nodes_to_patch:
        monkeypatch_hash_objects(
            monkeypatch,
            node_class,  #type: ignore[arg-type]
            mock_objects_to_hash
        )
