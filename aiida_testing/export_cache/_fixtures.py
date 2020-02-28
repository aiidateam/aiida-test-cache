# -*- coding: utf-8 -*-
"""
Defines a pytest fixture for automatically enable caching in tests and exports an aiida graph if not existent.
Meant to be useful for WorkChain tests.
"""

import uuid
import shutil
import inspect
import pathlib
import typing as ty

import pytest

from ._env_keys import EnvKeys
from .._config import get_config

__all__ = ("run_with_cache")

'''
@pytest.fixture(scope='function')
def run_with_cache():
    """
    Fixture to automatically import an aiida graph for a given process builder.
    """

    def _run_with_cache(
        builder: aiida process builder class,
        label: str = '',
        #data_dir_abspath: ty.Union[str, pathlib.Path],
        #ignore_nodes: ty.Iterable[str] = ('_aiidasubmit.sh', )
    ):
        """
        Function, which checks if a aiida export for a given Process builder exists,
        if it does it imports the aiida graph and runs the builder with caching.
        If the cache does not exists, it still runs the builder but creates an
        export afterwards.

        Inputs:

        builder : AiiDA Process builder class,
        data_dir_abspath : optional
            Absolute path of the directory where the exported workchain graphs are
            stored.

        ignore_nodes : list string, ignore input nodes with these labels/link labels to ignore in hash.
        # needed?
        """

        from aiida.common.hashing import make_hash
        from aiida.orm import ProcessNode, QueryBuilder
        from aiida.tools.importexport import import_data
        from aiida.tools.importexport import export
        from aiida.engine import run_get_node
        from aiida.manage.caching import enable_caching
        from aiida.manage.caching import get_use_cache

        cache_exists = False

        cwd = pathlib.Path(os.getcwd())                  # Might be not the best idea.
        data_dir = (cwd / 'data_dir')                    # TODO: get from config?
        hash = make_hash(builder)
        process_class = builder.process_class
        name = label + str(process_class).split('.')[-1].strip("'>") + 'nodes' + hash

        # check existence
        full_import_path = datadir + '/' + name + '.tar.gz'

        cache_path = pathlib.Path(full_import_path)
        if cache_path.exists():
            cache_exists = True

        if cache_exists:
            # import data from previous run to use caching
            import_data(full_import_path, extras_mode_existing='ncu', extras_mode_new='import')

            # need to rehash after import, otherwise cashing does not work
            qb = QueryBuilder()
            qb.append(ProcessNode, tag='node') # query for all ProcessNodes
            to_hash = qb.all()
            #num_nodes = qb.count()
            #print(num_nodes, to_hash)
            for node in to_hash:
                node[0].rehash()

        # now run calculation
        # TODO: I am not yet convinced that it is a good idea to run this inside the fixture,
        # alternatively end fixture here and write a second one for the export.
        with enable_caching(): # should enable caching globally in this python interpreter
            out, node = run_get_node(builder)

        if not cache_exits:
            # TODO create datadir if not existent
            # export data to reuse it later
            export([node], outfile=full_import_path, overwrite=True) # add export of extras automatically

        return out, node

    return _run_with_cash

'''
