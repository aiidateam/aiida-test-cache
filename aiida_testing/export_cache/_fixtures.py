# -*- coding: utf-8 -*-
"""
Defines pytest fixtures for automatically enable caching in tests and export aiida graphs if not existent.
Meant to be useful for WorkChain tests.
"""
# pylint: disable=unused-argument, protected-access, redefined-outer-name

import os
import hashlib
import pathlib
import typing as ty
import pytest
from aiida.engine import run_get_node
from aiida.engine import ProcessBuilderNamespace
from aiida.common.hashing import make_hash
from aiida.orm import Node, Code, Dict, SinglefileData, List, FolderData, RemoteData
from aiida.orm import CalcJobNode, ProcessNode  #, load_node
from aiida.orm.querybuilder import QueryBuilder
from aiida.manage.caching import enable_caching
from contextlib import contextmanager

__all__ = (
    "run_with_cache", "load_cache", "export_cache", "with_export_cache", "hash_code_by_entrypoint"
)

#### utils


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


@pytest.fixture(scope='function')
def export_cache(hash_code_by_entrypoint):
    """Fixture to export an AiiDA graph from given node(s)"""
    def _export_cache(node, savepath, default_data_dir=None, overwrite=True):
        """
        Function to export an AiiDA graph from a given node.
        Currenlty, uses the export functionalities of aiida-core

        :param node: AiiDA node which graph is to be exported, or list of nodes
        :param savepath: str or path where the export file is to be saved
        :param overwrite: bool, default=True, if existing export is overwritten
        """
        from aiida.tools.importexport import export

        # we rehash before the export, what goes in the hash is monkeypatched
        qub = QueryBuilder()
        qub.append(ProcessNode)  # rehash all ProcesNodes
        to_hash = qub.all()
        for node1 in to_hash:
            node1[0].rehash()

        if os.path.isabs(savepath):
            full_export_path = savepath
        else:
            if default_data_dir is None:
                default_data_dir = os.path.join(os.getcwd(), 'data_dir')  # May not be best idea
            full_export_path = os.path.join(default_data_dir, savepath)
            #print(full_export_path)

        if isinstance(node, list):
            to_export = node
        else:
            to_export = [node]
        export(
            to_export, outfile=full_export_path, overwrite=overwrite, include_comments=True
        )  # extras are automatically included

    return _export_cache


# Do we always want to use hash_code_by_entrypoint here?
@pytest.fixture(scope='function')
def load_cache(hash_code_by_entrypoint):
    """Fixture to load a cached AiiDA graph"""
    def _load_cache(path_to_cache=None, node=None, load_all=False):
        """
        Function to import an AiiDA graph

        :param path_to_cache: str or path to the AiiDA export file to load,
            if path_to_cache points to a directory, all import files in this dir are imported

        :param node: AiiDA node which cache to load,
            if no path_to_cache is given tries to guess it.
        :raises : OSError, if import file non existent
        """
        from aiida.tools.importexport import import_data

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
            # TODO: what about relative path to data_dir
            full_import_path = pathlib.Path(path_to_cache)

        if full_import_path.exists():
            if os.path.isfile(full_import_path):
                # import cache, also import extras
                import_data(full_import_path, extras_mode_existing='ncu', extras_mode_new='import')
            elif os.path.isdir(full_import_path):
                for filename in os.listdir(full_import_path):
                    file_full_import_path = os.path.join(full_import_path, filename)
                    # we curretly assume all files are valid aiida exports...
                    # maybe check if valid aiida export, or catch exception
                    import_data(
                        file_full_import_path, extras_mode_existing='ncu', extras_mode_new='import'
                    )
            else:  # Should never get there
                raise OSError(
                    "Path: {} to be imported exists, but is neither a file or directory.".
                    format(full_import_path)
                )
        else:
            raise OSError("File: {} to be imported does not exist.".format(full_import_path))

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
def with_export_cache(export_cache, load_cache):
    """
    Fixture to use in a with() environment within a test to enable caching in the with-statement.
    Requires to provide an absolutpath to the export file to load or export to.
    Export the provenance of all calcjobs nodes within the test.
    """
    @contextmanager
    def _with_export_cache(data_dir_abspath, calculation_class=None):
        """
        Function
        """

        # check and load export
        export_exists = os.path.isfile(data_dir_abspath)
        if export_exists:
            load_cache(path_to_cache=data_dir_abspath)

        # default enable globally for all jobcalcs
        if calculation_class is None:
            identifier = None
        else:
            identifier = calculation_class.build_process_type()
        with enable_caching(identifier=identifier):
            yield  # now the test runs

        # This is executed after the test
        if not export_exists:
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
            export_cache(node=to_export, savepath=data_dir_abspath)

    return _with_export_cache


@pytest.fixture
def hash_code_by_entrypoint(monkeypatch):
    """
    Monkeypatch .get_objects_to_hash of Code and CalcJobNodes of aiida-core
    to not include the uuid of the computer and less information of the code node in the hash
    """
    from aiida.common.links import LinkType

    def mock_objects_to_hash_code(self):
        """
        Return a list of objects which should be included in the hash of a Code node
        """
        # computer names are changed by aiida-core if imported and do not have same uuid.
        return [self.get_attribute(key='input_plugin')]  #, self.get_computer_name()]

    def mock_objects_to_hash_calcjob(self):
        """
        Return a list of objects which should be included in the hash of a CalcJobNode.
        code from aiida-core, only self.computer.uuid is commented out
        """
        #from pprint import pprint
        #from importlib import import_module
        ignored = list(self._hash_ignored_attributes)
        ignored.append('version')
        objects = [
            #import_module(self.__module__.split('.', 1)[0]).__version__,
            {
                key: val
                for key, val in self.attributes_items()
                if key not in ignored and key not in self._updatable_attributes
            },
            #self.computer.uuid if self.computer is not None else None,
            {
                entry.link_label: entry.node.get_hash()
                for entry in
                self.get_incoming(link_type=(LinkType.INPUT_CALC, LinkType.INPUT_WORK))
                if entry.link_label not in self._hash_ignored_inputs
            }
        ]
        #pprint('{} objects to hash calcjob: {}'.format(type(self), objects))
        return objects

    monkeypatch.setattr(Code, "_get_objects_to_hash", mock_objects_to_hash_code)
    monkeypatch.setattr(CalcJobNode, "_get_objects_to_hash", mock_objects_to_hash_calcjob)

    # for all other data, since they include the version

    def mock_objects_to_hash(self):
        """
        Return a list of objects which should be included in the hash of all Nodes.
        """
        ignored = list(self._hash_ignored_attributes)  # pylint: disable=protected-access
        ignored.append('version')
        self._hash_ignored_attributes = tuple(ignored)  # pylint: disable=protected-access

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
    classes_to_patch = [Dict, SinglefileData, List, FolderData, RemoteData]
    for classe in classes_to_patch:
        monkeypatch.setattr(classe, "_get_objects_to_hash", mock_objects_to_hash)

    #BaseData, List, Array, ...


@pytest.fixture(scope='function')
def run_with_cache(export_cache, load_cache):
    """
    Fixture to automatically import an aiida graph for a given process builder.
    """
    def _run_with_cache( # type: ignore
        builder: ty.Union[dict, ProcessBuilderNamespace
                          ],  #aiida process builder class, or dict, if process class is given
        process_class=None,
        label: str = '',
        data_dir: ty.Union[str, pathlib.Path] = 'data_dir',
    ):
        """
        Function, which checks if a aiida export for a given Process builder exists,
        if it does it imports the aiida graph and runs the builder with caching.
        If the cache does not exists, it still runs the builder but creates an
        export afterwards.

        Inputs:

        builder : AiiDA Process builder class,
        data_dir: optional
            Absolute path of the directory where the exported workchain graphs are
            stored.

        ignore_nodes : list string, ignore input nodes with these labels/link labels to ignore in hash.
        # needed?
        """

        cache_exists = False
        if data_dir == 'data_dir':
            cwd = pathlib.Path(os.getcwd())  # Might be not the best idea.
            data_dir = (cwd / 'data_dir')  # TODO: get from config?

        bui_hash, input_nodes = get_hash_process(builder)  # pylint: disable=unused-variable

        if process_class is None:  # and isinstance(builder, dict):
            process_class = builder.process_class  # type: ignore
            # we assume ProcessBuilder, since type(ProcessBuilder) is abc
        #else:
        #    raise TypeError(
        #        'builder has to be of type ProcessBuilder if no process_class is specified'
        #    )
        name = label + str(process_class).split('.')[-1].strip("'>") + '-nodes-' + bui_hash
        print(name)

        # check existence
        full_import_path = str(data_dir) + '/' + name + '.tar.gz'
        print(full_import_path)
        cache_path = pathlib.Path(full_import_path)
        if cache_path.exists():
            cache_exists = True

        if cache_exists:
            # import data from previous run to use caching
            load_cache(path_to_cache=full_import_path)

        # now run process/workchain whatever
        with enable_caching():  # should enable caching globally in this python interpreter
            #yield #test is running
            #res, resnode = run_get_node(builder)
            res, resnode = run_get_node(process_class, **builder)

        # This is executed after the test
        if not cache_exists:
            # TODO create datadir if not existent

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
            export_cache(node=resnode, savepath=full_import_path)

        return res, resnode

    return _run_with_cache
