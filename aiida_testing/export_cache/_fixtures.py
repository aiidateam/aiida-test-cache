# -*- coding: utf-8 -*-
"""
Defines a pytest fixture for automatically enable caching in tests and exports an aiida graph if not existent
"""

import uuid
import shutil
import inspect
import pathlib
import typing as ty

import pytest

from ._env_keys import EnvKeys
from .._config import get_config

__all__ = ("mock_code_factory", )

'''
@pytest.fixture(scope='function')
def with_cache():
    """
    Fixture to automatically import a aiida graph and .
    
    def _with_cache(
        label: str
        data_dir_abspath: ty.Union[str, pathlib.Path],
        #ignore_nodes: ty.Iterable[str] = ('_aiidasubmit.sh', )
    ):
        """

        Parameters
        data_dir_abspath :
            Absolute path of the directory where the exported workchain graphs are
            stored.
        """
        
        cache_exists = False
        # import data from previous run to use caching
        from aiida.tools.importexport import import_data
        

        import_data('files/export_kkr_startpot.tar.gz', extras_mode_existing='ncu', extras_mode_new='import')


        # need to rehash after import, otherwise cashing does not work
        from aiida.orm import Data, ProcessNode, QueryBuilder
        entry_point = (Data, ProcessNode)
        qb = QueryBuilder()
        qb.append(ProcessNode, tag='node') # query for ProcessNodes
        to_hash = qb.all()
        #num_nodes = qb.count()
        #print(num_nodes, to_hash)
        for node in to_hash:
            node[0].rehash()

        # now run calculation
        from aiida.engine import run_get_node #run
        from aiida.manage.caching import enable_caching
        from aiida.manage.caching import get_use_cache
        with enable_caching(): # should enable caching globally in this python interpreter
            out, node = run_get_node(builder)
        
        if not cache_exits:
            # export data to reuse it later
            #from aiida.tools.importexport import export
            #export([node], outfile='export_data.aiida.tar.gz', overwrite=True) # add export of extras automatically


            

        return out, node

    return _with_cash

'''
