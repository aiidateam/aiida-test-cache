# -*- coding: utf-8 -*-
"""
Defines pytest fixtures for automatically enable caching in tests and export aiida graphs if not existent.
Meant to be useful for WorkChain tests.
"""
import os
import uuid
import shutil
import hashlib
import inspect
import pathlib
import typing as ty
import pytest
#from .._config import get_config
from aiida_testing._config import get_config
from aiida.engine import ProcessBuilder
import pathlib

__all__ = ("run_with_cache", "load_cache", "export_cache")



#### utils

def unnest_dict(nested_dict):
    """
    Returns a simple dictionary from a possible arbitray nested dictionary
    by adding keys in dot notation, rekrusively
    """
    new_dict = {}
    for key, val in nested_dict.items():
        if isinstance(val, dict):
            unval = unnest_dict(val)              #rekursive!
            for k, v in unval.items():
                key_new = str(key) + '.' + str(k)
                new_dict[key_new] = v
        else:
            new_dict[str(key)] = val
    return new_dict

def get_hash_process(builder, input_nodes=[]):
    """ creates a hash from a builder/dictionary of inputs"""
    from aiida.common.hashing import make_hash
    from aiida.orm import Node, Code
    import hashlib

    # hashing the builder
    # currently workchains are not hashed in AiiDA so we create a hash for the filename
    unnest_builder = unnest_dict(builder)
    md5sum = hashlib.md5()
    for key, val in sorted(unnest_builder.items()):
        if isinstance(val, Code):
           continue # we do not include the code in the hash, might be mocked
           #TODO include the code to some extent
        if isinstance(val, Node):
            if not val.is_stored:
               val.store()
            val_hash = val.get_hash()         # only works if nodes are stored!
            input_nodes.append(val)
        else:
            val_hash = make_hash(val)
        md5sum.update(val_hash.encode())
    bui_hash = md5sum.hexdigest()

    return bui_hash, input_nodes

####

#### fixtures

@pytest.fixture(scope='function')
def export_cache():
    """Fixture to export an AiiDA graph from a given node"""

    def _export_cache(node, savepath, overwrite=True):
        """
        Function to export an AiiDA graph from a given node.

        :param node: AiiDA node which graph is to be exported
        :param savepath: str or path where the export file is to be saved
        :param overwrite: bool, default=True, if existing export is overwritten
        """
        from aiida.tools.importexport import export

        # TODO: if relativ savepath get default data dir
        full_export_path = savepath

        export([node], outfile=full_export_path, overwrite=overwrite,
               include_comments=True)      # extras are automatically

    return _export_cache


@pytest.fixture(scope='function')
def load_cache():
    """Fixture to load a cached AiiDA graph"""
    def _load_cache(path_to_cache=None, node=None, load_all=False):
        """
        Function to import an AiiDA graph

        :param path_to_cache: str or path to the AiiDA export file to load,
            if path_to_cache points to a directory, all import files in this dir are imported

        :param node: AiiDA node which cache to load,
            if no path_to_cache is given tries to guess it.
        """
        from aiida.tools.importexport import import_data
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm import ProcessNode

        if path_to_cache is None:
            if node is None:
                raise ValueError("Node argument can not be None "
                                 "if no explicit 'path_to_cache' is specified")
            else:    # create path from node
                pass
                # get default data dir
                # get hash for give node
                # construct path from that
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
                    import_data(file_full_import_path, extras_mode_existing='ncu', extras_mode_new='import')
            else: # Should never get there
                raise OSError("Path: {} to be imported exists, but is neither a file or directory.".format(full_import_path))
        else:
            raise OSError("File: {} to be imported does not exist.".format(full_import_path))

        # need to rehash after import, otherwise cashing does not work
        # for this we rehash all process nodes
        # this way we use the full caching mechanism of aiida-core.
        # currently this should only cache CalcJobNodes
        qb = QueryBuilder()
        qb.append(ProcessNode, tag='node') # query for all ProcesNodes
        to_hash = qb.all()
        for node in to_hash:
            node[0].rehash()

    return _load_cache


@pytest.fixture(scope='function')
def run_with_cache(export_cache, load_cache):
    """
    Fixture to automatically import an aiida graph for a given process builder.
    """

    def _run_with_cache(
        builder: ProcessBuilder, #aiida process builder class, or dict, if process class is given
        process_class = None,
        label: str = '',
        data_dir: ty.Union[str, pathlib.Path] = None,
        #ignore_nodes: ty.Iterable[str] = ('_aiidasubmit.sh', )
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

        from aiida.common.hashing import make_hash
        from aiida.orm import ProcessNode, QueryBuilder, Node, Code, load_node
        from aiida.tools.importexport import import_data
        from aiida.tools.importexport import export
        from aiida.engine import run_get_node
        from aiida.manage.caching import enable_caching
        from aiida.manage.caching import get_use_cache

        cache_exists = False
        if data_dir is None:
            cwd = pathlib.Path(os.getcwd())               # Might be not the best idea.
            data_dir = (cwd / 'data_dir')                 # TODO: get from config?


        bui_hash, input_nodes = get_hash_process(builder)
        print(bui_hash)

        if process_class is None:
            process_class = builder.process_class
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
        with enable_caching(): # should enable caching globally in this python interpreter
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
            union = set()
            for node in input_nodes:
                pks = set([ent.node.pk for ent in node.get_outgoing().all()])
                union = union.union(pks)
            if len(union) != 0:
                process_node_pk = min(union)
                #export data to reuse it later
                export_cache(node=load_node(process_node_pk), savepath=full_import_path)
            else:
                print('could not find the process node')
            # if no yield
            #export_cache(node=resnode, savepath=full_import_path)

        return res, resnode
    return _run_with_cache
