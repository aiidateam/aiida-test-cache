# -*- coding: utf-8 -*-
"""
Defines pytest fixtures for automatically enable caching in tests and create aiida archives if not existent.
Meant to be useful for WorkChain tests.
"""
# pylint: disable=unused-argument, protected-access, redefined-outer-name

import os
import pathlib
from functools import partial
from contextlib import contextmanager
import shutil
import typing as ty

import pytest

from aiida import plugins
from aiida.common.links import LinkType
from aiida.orm import Code, Dict, SinglefileData, List, FolderData, RemoteData, StructureData
from aiida.orm import CalcJobNode, QueryBuilder, Node
from aiida.manage.caching import enable_caching
from aiida.cmdline.utils.echo import echo_warning

from ._utils import rehash_processes, monkeypatch_hash_objects, get_node_from_hash_objects_caller
from .._config import Config

__all__ = (
    "pytest_addoption", "absolute_archive_path", "load_node_archive", "create_node_archive",
    "enable_archive_cache", "liberal_hash", "archive_cache_forbid_migration",
    "import_with_migrate_fixture"
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add pytest command line options."""
    parser.addoption(
        "--archive-cache-forbid-migration",
        action="store_true",
        default=False,
        help="If True the stored archives cannot be migrated if their versions are incompatible."
    )


@pytest.fixture(scope='session')
def archive_cache_forbid_migration(request: pytest.FixtureRequest) -> bool:
    """Read whether aiida is forbidden from migrating the test archives if their versions are incompatible."""
    return request.config.getoption( #type:ignore [no-any-return]
        "--archive-cache-forbid-migration"
    )


#Cross-compatible fixture for import AiiDA archives in 1.X and 2.X
try:
    from aiida.tools.archive import create_archive
    from aiida.tools.archive import import_archive
    import_archive = partial(import_archive, merge_extras=('n', 'c', 'u'), import_new_extras=True)

    @pytest.fixture(scope='function', name="import_with_migrate")
    def import_with_migrate_fixture(archive_cache_forbid_migration: bool) -> ty.Callable:
        """
        Import AiiDA Archive. If the version is incompatible
        try to migrate the archive if --archive-cache-forbid-migration option is not specified
        """

        def _import_with_migrate(
            archive_path: ty.Union[str, pathlib.Path], *args: ty.Any, **kwargs: ty.Any
        ) -> None:
            """
            Import AiiDA Archive. If the version is incompatible
            try to migrate the archive if --archive-cache-forbid-migration option is not specified
            """
            #pylint: disable=import-outside-toplevel
            from aiida.tools.archive import get_format
            from aiida.common.exceptions import IncompatibleStorageSchema

            try:
                import_archive(archive_path, *args, **kwargs)
            except IncompatibleStorageSchema:
                if not archive_cache_forbid_migration:
                    echo_warning(
                        f'incompatible version detected for {archive_path}, trying migration'
                    )
                    archive_format = get_format()
                    version = archive_format.latest_version
                    archive_format.migrate(
                        archive_path, archive_path, version, force=True, compression=6
                    )
                    import_archive(archive_path, *args, **kwargs)
                else:
                    raise

        return _import_with_migrate

except ImportError:
    from aiida.tools.importexport import export as create_archive  #type: ignore[import,no-redef]
    from aiida.tools.importexport import import_data as import_archive  #type: ignore[no-redef]
    import_archive = partial(import_archive, extras_mode_existing='ncu', extras_mode_new='import')

    @pytest.fixture(scope='function', name="import_with_migrate")
    def import_with_migrate_fixture(temp_dir, archive_cache_forbid_migration):
        """
        Import AiiDA Archive. If the version is incompatible
        try to migrate the archive if --archive-cache-forbid-migration option is not specified
        """

        def _import_with_migrate(archive_path, *args, **kwargs):
            """
            Import AiiDA Archive. If the version is incompatible
            try to migrate the archive if --archive-cache-forbid-migration option is not specified
            """
            #pylint: disable=import-outside-toplevel
            from aiida.tools.importexport import EXPORT_VERSION, IncompatibleArchiveVersionError
            # these are only availbale after aiida >= 1.5.0, maybe rely on verdi import instead
            from aiida.tools.importexport import detect_archive_type
            from aiida.tools.importexport.archive.migrators import get_migrator  #type: ignore[import]

            try:
                import_archive(archive_path, *args, **kwargs)
            except IncompatibleArchiveVersionError:
                if not archive_cache_forbid_migration:
                    echo_warning(
                        f'incompatible version detected for {archive_path}, trying migration'
                    )
                    migrator = get_migrator(detect_archive_type(archive_path))(archive_path)
                    archive_path = migrator.migrate(
                        EXPORT_VERSION, None, out_compression='none', work_dir=temp_dir
                    )
                    import_archive(archive_path, *args, **kwargs)
                else:
                    raise

        return _import_with_migrate


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
        :param overwrite: If True the existing archive is supposed to be replaced at the end of the test

        .. note::

            If the archive at the determined absolute path exists, is allowed to be migrated
            , i.e. the `--archive-cache-forbid-migration` options is not specified,
            and overwrite is False, the archive will be copied into a temporary directory created by
            pytest

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
def create_node_archive(liberal_hash: None, absolute_archive_path: ty.Callable) -> ty.Callable:
    """Fixture to create an AiiDA archive from given node(s)"""

    def _create_node_archive(
        nodes: ty.Union[Node, ty.List[Node]],
        archive_path: ty.Union[str, pathlib.Path],
        overwrite: bool = True
    ) -> None:
        """
        Function to export an AiiDA graph from a given node.
        Uses the export functionalities of aiida-core

        :param node: AiiDA node or list of nodes from whose graph the archive should be created
        :param archive_path: str or path where the export file is to be saved
        :param overwrite: bool, default=True, if True any existing export is overwritten
        """

        # rehash before the export, since what goes in the hash is monkeypatched
        rehash_processes()
        full_export_path = absolute_archive_path(archive_path, overwrite=overwrite)

        if isinstance(nodes, list):
            to_export = nodes
        else:
            to_export = [nodes]

        create_archive(
            to_export, filename=full_export_path, overwrite=overwrite, include_comments=True
        )  # extras are automatically included

    return _create_node_archive


@pytest.fixture(scope='function')
def load_node_archive(
    liberal_hash: None, absolute_archive_path: ty.Callable, import_with_migrate: ty.Callable
) -> ty.Callable:
    """Fixture to load a cached AiiDA graph"""

    def _load_node_archive(archive_path: ty.Union[str, pathlib.Path]) -> None:
        """
        Function to import an AiiDA graph

        :param archive_path: str or path to the AiiDA archive file to load
        :raises : FileNotFoundError, if import file is non existent
        """
        # relative paths given will be completed with cwd
        full_import_path = absolute_archive_path(archive_path)

        if os.path.exists(full_import_path) and os.path.isfile(full_import_path):
            # import cache, also import extras
            import_with_migrate(full_import_path)
        else:
            raise FileNotFoundError(f"File: {full_import_path} to be imported does not exist.")

        # need to rehash after import, otherwise cashing does not work
        # for this we rehash all process nodes
        # this way we use the full caching mechanism of aiida-core.
        # currently this should only cache CalcJobNodes
        rehash_processes()

    return _load_node_archive


@pytest.fixture(scope='function')
def enable_archive_cache(
    create_node_archive: ty.Callable, load_node_archive: ty.Callable,
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
        calculation_class: ty.Union[ty.Type[CalcJobNode], ty.Sequence[ty.Type[CalcJobNode]],
                                    None] = None,
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

        full_archive_path = absolute_archive_path(archive_path, overwrite=overwrite)
        # check and load export
        export_exists = os.path.isfile(full_archive_path)
        if export_exists:
            load_node_archive(full_archive_path)

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
            queryclass: ty.Union[ty.Type[CalcJobNode], ty.Sequence[ty.Type[CalcJobNode]]]
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
        plugins.DataFactory(entry_point): tuple(set(ignored)) + ('version', )
        for entry_point, ignored in hash_ignore_config.get('node_attributes', {}).items()
    }
    calcjob_ignored_attributes = tuple(hash_ignore_config.get('calcjob_attributes', [])
                                       ) + ('version', )
    calcjob_ignored_inputs = tuple(hash_ignore_config.get('calcjob_inputs', []))

    def mock_objects_to_hash_code(self):
        """
        Return a list of objects which should be included in the hash of a Code node
        """
        self = get_node_from_hash_objects_caller(self)
        # computer names are changed by aiida-core if imported and do not have same uuid.
        return [self.get_attribute(key='input_plugin')]

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
            for key, val in self.attributes_items()
            if key not in self._hash_ignored_attributes and key not in self._updatable_attributes
        },
                   {
                       entry.link_label: entry.node.get_hash()
                       for entry in
                       self.get_incoming(link_type=(LinkType.INPUT_CALC, LinkType.INPUT_WORK))
                       if entry.link_label not in hash_ignored_inputs
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
                for key, val in self.attributes_items() if key not in self._hash_ignored_attributes
                and key not in self._updatable_attributes
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
