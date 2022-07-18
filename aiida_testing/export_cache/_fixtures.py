# -*- coding: utf-8 -*-
"""
Defines pytest fixtures for automatically enable caching in tests and export aiida graphs if not existent.
Meant to be useful for WorkChain tests.
"""
# pylint: disable=unused-argument, protected-access, redefined-outer-name

import os
import hashlib
import pathlib
from functools import partial
from contextlib import contextmanager
import typing as ty
import pytest

from aiida import plugins
from aiida.engine import run_get_node
from aiida.engine import ProcessBuilderNamespace
from aiida.common.hashing import make_hash
from aiida.common.links import LinkType
from aiida.orm import Node, Code, Dict, SinglefileData, List, FolderData, RemoteData, StructureData
from aiida.orm import CalcJobNode, ProcessNode  #, load_node
from aiida.orm.querybuilder import QueryBuilder
from aiida.manage.caching import enable_caching

try:
    from aiida.tools.archive import create_archive
    from aiida.tools.archive import import_archive
    import_archive = partial(import_archive, merge_extras=('n', 'c', 'u'), import_new_extras=True)

    @pytest.fixture(scope='function', name="import_with_migrate")
    def import_with_migrate_fixture():
        """
        Import AiiDA Archive. If the version is incompatible
        try to migrate the archive
        """
        def _import_with_migrate(archive_path, *args, **kwargs):
            from click import echo
            from aiida.tools.archive import get_format
            from aiida.common.exceptions import IncompatibleStorageSchema

            try:
                import_archive(archive_path, *args, **kwargs)
            except IncompatibleStorageSchema:
                echo(f'incompatible version detected for {archive_path}, trying migration')
                archive_format = get_format()
                version = archive_format.latest_version
                archive_format.migrate(archive_path, archive_path, version, force=True, compression=6)
                import_archive(archive_path, *args, **kwargs)

        return _import_with_migrate

except ImportError:
    from aiida.tools.importexport import export as create_archive
    from aiida.tools.importexport import import_data as import_archive
    import_archive = partial(import_archive, extras_mode_existing='ncu', extras_mode_new='import')

    @pytest.fixture(scope='function', name="import_with_migrate")
    def import_with_migrate_fixture(temp_dir):
        """
        Import AiiDA Archive. If the version is incompatible
        try to migrate the archive
        """
        def _import_with_migrate(archive_path, *args, **kwargs):
            from click import echo
            from aiida.tools.importexport import EXPORT_VERSION, IncompatibleArchiveVersionError
            # these are only availbale after aiida >= 1.5.0, maybe rely on verdi import instead
            from aiida.tools.importexport import detect_archive_type
            from aiida.tools.importexport.archive.migrators import get_migrator

            try:
                import_archive(archive_path, *args, **kwargs)
            except IncompatibleArchiveVersionError:
                echo(f'incompatible version detected for {archive_path}, trying migration')
                migrator = get_migrator(detect_archive_type(archive_path))(archive_path)
                archive_path = migrator.migrate(EXPORT_VERSION, None, out_compression='none', work_dir=temp_dir)
                import_archive(archive_path, *args, **kwargs)
        
        return _import_with_migrate

__all__ = (
    "pytest_addoption", "absolute_archive_path", "run_with_cache", "load_cache", "export_cache",
    "with_export_cache", "hash_code_by_entrypoint", "export_cache_allow_migration", "import_with_migrate_fixture"
)

#### utils


def pytest_addoption(parser):
    """Add pytest command line options."""
    parser.addoption(
        "--export-cache-allow-migration",
        action="store_true",
        default=False,
        help="If True the stored archives can be migrated if needed."
    )


def unnest_dict(nested_dict: ty.Union[dict, ProcessBuilderNamespace]) -> dict:  # type: ignore
    """
    Returns a simple dictionary from a possible arbitray nested dictionary
    or Aiida ProcessBuilderNamespace by adding keys in dot notation, rekrusively
    """
    new_dict = {}
    for key, val in nested_dict.items():
        if isinstance(val, (dict, ProcessBuilderNamespace)):
            unval = unnest_dict(val)  #rekursive!
            for key2, val2 in unval.items():
                key_new = str(key) + '.' + str(key2)
                new_dict[key_new] = val2
        else:
            new_dict[str(key)] = val  # type: ignore
    return new_dict


def get_hash_process(  # type: ignore # pylint: disable=dangerous-default-value
    builder: ty.Union[dict, ProcessBuilderNamespace],
    input_nodes: list = []
):
    """ creates a hash from a builder/dictionary of inputs"""

    # hashing the builder
    # currently workchains are not hashed in AiiDA so we create a hash for the filename
    unnest_builder = unnest_dict(builder)
    md5sum = hashlib.md5()
    for key, val in sorted(unnest_builder.items()):  # pylint: disable=unused-variable
        if isinstance(val, Code):
            continue  # we do not include the code in the hash, might be mocked
            #TODO include the code to some extent
        if isinstance(val, Node):
            if not val.is_stored:
                val.store()
            val_hash = val.get_hash()  # only works if nodes are stored!
            input_nodes.append(val)
        else:
            val_hash = make_hash(val)
        md5sum.update(val_hash.encode())
    bui_hash = md5sum.hexdigest()

    return bui_hash, input_nodes


####

#### fixtures


@pytest.fixture(scope='session')
def export_cache_allow_migration(request):
    """Read whether to regenerate test data from command line option."""
    return request.config.getoption("--export-cache-allow-migration")


@pytest.fixture(scope='function')
def absolute_archive_path(request, testing_config):
    """
    Fixture to get the absolute filepath for a given archive
    """

    export_cache_config = testing_config.get('export_cache', {})

    def _absolute_archive_path(filepath):
        """
        Returns the absolute filepath to the given archive.
        The procedure is:

        - If the path is already absolute, return it
        - If the option default_cache_dir is given construct it relative to this
        - Otherwise interpret the directory as relative to the test file inside a folder `caches`
        """
        default_data_dir = export_cache_config.get('default_data_dir', '')
        filepath = pathlib.Path(filepath)

        if filepath.is_absolute():
            full_export_path = filepath
        else:
            if not default_data_dir:
                #Adapted from shared_datadir of pytest-datadir to not use paths
                #in the tmp copies created by pytest
                default_data_dir = pathlib.Path(request.fspath.dirname) / 'caches'
            else:
                default_data_dir = pathlib.Path(default_data_dir)
            if not default_data_dir.exists():
                default_data_dir.mkdir()

            full_export_path = pathlib.Path(default_data_dir) / filepath
            #print(full_export_path)
        return os.fspath(full_export_path.absolute())

    return _absolute_archive_path


@pytest.fixture(scope='function')
def export_cache(hash_code_by_entrypoint, absolute_archive_path):
    """Fixture to export an AiiDA graph from given node(s)"""

    def _export_cache(node, savepath, overwrite=True):
        """
        Function to export an AiiDA graph from a given node.
        Currenlty, uses the export functionalities of aiida-core

        :param node: AiiDA node which graph is to be exported, or list of nodes
        :param savepath: str or path where the export file is to be saved
        :param overwrite: bool, default=True, if existing export is overwritten
        """

        # we rehash before the export, what goes in the hash is monkeypatched
        qub = QueryBuilder()
        qub.append(ProcessNode)  # rehash all ProcesNodes
        to_hash = qub.all()
        for node1 in to_hash:
            node1[0].rehash()

        full_export_path = absolute_archive_path(savepath)

        if isinstance(node, list):
            to_export = node
        else:
            to_export = [node]
        create_archive(
            to_export, filename=full_export_path, overwrite=overwrite, include_comments=True
        )  # extras are automatically included

    return _export_cache


# Do we always want to use hash_code_by_entrypoint here?
@pytest.fixture(scope='function')
def load_cache(hash_code_by_entrypoint, absolute_archive_path, export_cache_allow_migration, import_with_migrate):
    """Fixture to load a cached AiiDA graph"""

    def _load_cache(path_to_cache=None, node=None):
        """
        Function to import an AiiDA graph

        :param path_to_cache: str or path to the AiiDA export file to load,
            if path_to_cache points to a directory, all import files in this dir are imported

        :param node: AiiDA node which cache to load,
            if no path_to_cache is given tries to guess it.
        :raises : OSError, if import file non existent
        """
        if path_to_cache is None:
            if node is None:
                raise ValueError(
                    "Node argument can not be None "
                    "if no explicit 'path_to_cache' is specified"
                )
            #else:  # create path from node
            #    pass
            #    # get default data dir
            #    # get hash for give node
            #    # construct path from that
        else:
            # relative paths given will be completed with cwd
            full_import_path = absolute_archive_path(path_to_cache)

        if os.path.exists(full_import_path):
            if os.path.isfile(full_import_path):
                # import cache, also import extras
                if export_cache_allow_migration:
                    import_with_migrate(full_import_path)
                else:
                    import_archive(full_import_path)
            elif os.path.isdir(full_import_path):
                for filename in os.listdir(full_import_path):
                    file_full_import_path = os.path.join(full_import_path, filename)
                    # we curretly assume all files are valid aiida exports...
                    # maybe check if valid aiida export, or catch exception
                    if export_cache_allow_migration:
                        import_with_migrate(file_full_import_path)
                    else:
                        import_archive(file_full_import_path)
            else:  # Should never get there
                raise OSError(
                    f"Path: {full_import_path} to be imported exists, but is neither a file or directory."
                )
        else:
            raise FileNotFoundError(f"File: {full_import_path} to be imported does not exist.")

        # need to rehash after import, otherwise cashing does not work
        # for this we rehash all process nodes
        # this way we use the full caching mechanism of aiida-core.
        # currently this should only cache CalcJobNodes
        qub = QueryBuilder()
        qub.append(ProcessNode)  # query for all ProcesNodes
        to_hash = qub.all()
        for node1 in to_hash:
            node1[0].rehash()

    return _load_cache


@pytest.fixture(scope='function')
def with_export_cache(export_cache, load_cache, absolute_archive_path):
    """
    Fixture to use in a with() environment within a test to enable caching in the with-statement.
    Requires to provide an absolutpath to the export file to load or export to.
    Export the provenance of all calcjobs nodes within the test.
    """

    @contextmanager
    def _with_export_cache(data_dir_abspath, calculation_class=None, overwrite=False):
        """
        Contextmanager to run calculation within, which aiida graph gets exported
        """

        full_export_path = absolute_archive_path(data_dir_abspath)
        # check and load export
        export_exists = os.path.isfile(full_export_path)
        if export_exists:
            load_cache(path_to_cache=full_export_path)

        # default enable globally for all jobcalcs
        if calculation_class is None:
            identifier = None
        else:
            identifier = calculation_class.build_process_type()
        with enable_caching(identifier=identifier):
            yield  # now the test runs

        # This is executed after the test
        if not export_exists or overwrite:
            # in case of yield: is the db already cleaned?
            # create export of all calculation_classes
            # Another solution out of this is to check the time before and
            # after the yield and export ONLY the jobcalc classes created within this time frame
            if calculation_class is None:
                queryclass = CalcJobNode
            else:
                queryclass = calculation_class
            qub = QueryBuilder()
            qub.append(queryclass, tag='node')  # query for CalcJobs nodes
            to_export = [entry[0] for entry in qub.all()]
            export_cache(node=to_export, savepath=full_export_path, overwrite=overwrite)

    return _with_export_cache


@pytest.fixture
def hash_code_by_entrypoint(monkeypatch, testing_config):
    """
    Monkeypatch .get_objects_to_hash of Code, CalcJobNodes and core Data nodes of aiida-core
    to not include the uuid of the computer and less information of the code node in the hash
    and remove aiida-core version from hash
    """
    export_cache_config = testing_config.get('export_cache', {})

    #Load the corresponding entry points
    node_ignored_attributes = {
        plugins.DataFactory(entry_point): ignored
        for entry_point, ignored in export_cache_config.get('node_ignored_attributes', {})
    }

    def mock_objects_to_hash_code(self):
        """
        Return a list of objects which should be included in the hash of a Code node
        """
        try:
            self.get_attribute
        except AttributeError:
            self = self._node
        # computer names are changed by aiida-core if imported and do not have same uuid.
        return [self.get_attribute(key='input_plugin')]  #, self.get_computer_name()]

    def mock_objects_to_hash_calcjob(self):
        """
        Return a list of objects which should be included in the hash of a CalcJobNode.
        code from aiida-core, only self.computer.uuid is commented out
        """
        try:
            self._hash_ignored_attributes
            hash_ignored_inputs = self._hash_ignored_inputs
        except AttributeError:
            hash_ignored_inputs = self._hash_ignored_inputs
            self = self._node

        additional_ignored_inputs = tuple(
            set(export_cache_config.get('calcjob_ignored_inputs', []))
        )
        additional_ignored_attributes = tuple(
            set(export_cache_config.get('calcjob_ignored_attributes', []))
        )

        #from pprint import pprint
        #from importlib import import_module
        hash_ignored_inputs = tuple(hash_ignored_inputs) + \
                              additional_ignored_inputs
        self._hash_ignored_attributes = tuple(self._hash_ignored_attributes) + \
                                        ('version',) + \
                                        additional_ignored_attributes

        objects = [
            #import_module(self.__module__.split('.', 1)[0]).__version__,
            {
                key: val
                for key, val in self.attributes_items() if key not in self._hash_ignored_attributes
                and key not in self._updatable_attributes
            },
            #self.computer.uuid if self.computer is not None else None,
            {
                entry.link_label: entry.node.get_hash()
                for entry in
                self.get_incoming(link_type=(LinkType.INPUT_CALC, LinkType.INPUT_WORK))
                if entry.link_label not in hash_ignored_inputs
            }
        ]
        #pprint('{} objects to hash calcjob: {}'.format(type(self), objects))
        return objects

    try:
        monkeypatch.setattr(Code, "_get_objects_to_hash", mock_objects_to_hash_code)
        monkeypatch.setattr(CalcJobNode, "_get_objects_to_hash", mock_objects_to_hash_calcjob)
    except AttributeError:
        from aiida.orm.nodes.caching import NodeCaching
        from aiida.orm.nodes.process.calculation.calcjob import CalcJobNodeCaching

        class MockCodeNodeCaching(NodeCaching):
            """
            NodeCaching subclass with stripped down _get_objects_to_hash method
            """

            def _get_objects_to_hash(self):
                return mock_objects_to_hash_code(self)

        class MockCalcjobNodeCaching(CalcJobNodeCaching):
            """
            NodeCaching subclass with stripped down _get_objects_to_hash method
            """

            def _get_objects_to_hash(self):
                return mock_objects_to_hash_calcjob(self)

        monkeypatch.setattr(CalcJobNode, "_CLS_NODE_CACHING", MockCalcjobNodeCaching)
        monkeypatch.setattr(Code, "_CLS_NODE_CACHING", MockCodeNodeCaching)
    # for all other data, since they include the version

    def mock_objects_to_hash(self):
        """
        Return a list of objects which should be included in the hash of all Nodes.
        """
        try:
            self._hash_ignored_attributes
        except AttributeError:
            self = self._node

        class_name = self.__class__.__name__

        additional_ignored_attributes = tuple(set(node_ignored_attributes.get(class_name, [])))
        self._hash_ignored_attributes = tuple(self._hash_ignored_attributes) + \
                                        ('version',) + \
                                        additional_ignored_attributes

        objects = [
            #importlib.import_module(self.__module__.split('.', 1)[0]).__version__,
            {
                key: val
                for key, val in self.attributes_items() if key not in self._hash_ignored_attributes
                and key not in self._updatable_attributes
            },
            #self._repository._get_base_folder(),
            #self.computer.uuid if self.computer is not None else None
        ]
        #print('{} objects to hash: {}'.format(type(self), objects))
        return objects

    # since we still want versioning for plugin datatypes and calcs we only monkeypatch aiida datatypes
    classes_to_patch = [Dict, SinglefileData, List, FolderData, RemoteData, StructureData]
    for classe in classes_to_patch:
        try:
            monkeypatch.setattr(classe, "_get_objects_to_hash", mock_objects_to_hash)
        except AttributeError:
            from aiida.orm.nodes.caching import NodeCaching

            class MockNodeCaching(NodeCaching):
                """
                NodeCaching subclass with stripped down _get_objects_to_hash method
                """

                def _get_objects_to_hash(self):
                    return mock_objects_to_hash(self)

            monkeypatch.setattr(classe, "_CLS_NODE_CACHING", MockNodeCaching)

    #BaseData, List, Array, ...


@pytest.fixture(scope='function')
def run_with_cache(export_cache, load_cache, absolute_archive_path):
    """
    Fixture to automatically import an aiida graph for a given process builder.
    """
    def _run_with_cache( # type: ignore
        builder: ty.Union[dict, ProcessBuilderNamespace
                          ],  #aiida process builder class, or dict, if process class is given
        process_class=None,
        label: str = '',
        overwrite: bool = False,
        data_dir: ty.Union[str, pathlib.Path, None] = None
    ):
        """
        Function, which checks if a aiida export for a given Process builder exists,
        if it does it imports the aiida graph and runs the builder with caching.
        If the cache does not exists, it still runs the builder but creates an
        export afterwards.

        Inputs:

        builder : AiiDA Process builder class,
        overwrite: enforce exporting of a new cache
        #ignore_nodes : list string, ignore input nodes with these labels/link labels to ignore in hash.
        # needed?
        """

        cache_exists = False
        bui_hash, _ = get_hash_process(builder)  # pylint: disable=unused-variable

        if process_class is None:  # and isinstance(builder, dict):
            process_class = builder.process_class  # type: ignore
            # we assume ProcessBuilder, since type(ProcessBuilder) is abc
        #else:
        #    raise TypeError(
        #        'builder has to be of type ProcessBuilder if no process_class is specified'
        #    )
        name = f"{label}{process_class.__name__}-nodes-{bui_hash}"
        path = name
        if data_dir is not None:
            path = os.fspath(pathlib.Path(data_dir) / name)
        full_import_path = absolute_archive_path(f"{path}.tar.gz")

        print(full_import_path)
        if os.path.exists(full_import_path):
            cache_exists = True

        if cache_exists:
            # import data from previous run to use caching
            load_cache(path_to_cache=full_import_path)

        # now run process/workchain whatever
        with enable_caching():  # should enable caching globally in this python interpreter
            if isinstance(builder, dict):
                res, resnode = run_get_node(process_class, **builder)
            else:
                res, resnode = run_get_node(builder)

        # This is executed after the test
        if not cache_exists or overwrite:

            # in case of yield:
            # is the db already cleaned?
            # since we do not the stored process node we try to get it from the inputs,
            # i.e to which node they are all connected, with the lowest common pk
            #union_pk: ty.Set[int] = set()
            #for node in input_nodes:
            #    pks = {ent.node.pk for ent in node.get_outgoing().all()}
            #    union_pk = union_pk.union(pks)
            #if len(union_pk) != 0:
            #    process_node_pk = min(union_pk)
            #    #export data to reuse it later
            #    export_cache(node=load_node(process_node_pk), savepath=full_import_path)
            #else:
            #    print("could not find the process node, don't know what to export")

            # if no yield
            export_cache(node=resnode, savepath=full_import_path, overwrite=overwrite)

        return res, resnode

    return _run_with_cache
