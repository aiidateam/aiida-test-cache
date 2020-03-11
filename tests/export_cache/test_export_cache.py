# -*- coding: utf-8 -*-
"""
Test basic usage of the mock code on examples using aiida-diff.
"""

import os
import tempfile

import pytest

from aiida.engine import run_get_node
from aiida.plugins import CalculationFactory, DataFactory
from aiida.engine import WorkChain, run, ToContext
from aiida.orm import Node, Code, SinglefileData

DiffParameters = DataFactory('diff')
DiffCalculation = CalculationFactory('diff')
CALC_ENTRY_POINT = 'diff'

#### diff workchain for basic tests

class DiffWorkChain(WorkChain):
    """
    Very simple workchain which wraps a diff calculation for testing purposes
    """
    @classmethod
    def define(cls, spec):
        super(DiffWorkChain, cls).define(spec)
        spec.expose_inputs(DiffCalculation, namespace='diff')
        spec.outline(
            cls.rundiff,
            cls.results,
        )
        spec.output('computed_diff')


    def rundiff(self):
        inputs = self.exposed_inputs(DiffCalculation, 'diff')
        running = self.submit(DiffCalculation, **inputs)

        return ToContext(diff_calc=running)

    def results(self):
        computed_diff = self.ctx.diff_calc.get_outgoing().get_node_by_label('diff')
        self.out('computed_diff', computed_diff)


#### tests

def test_export_cache(mock_code_factory, generate_diff_inputs, export_cache):
    """
    Basic test of the export cache fixture functionality,
    runs diff workchain and creates export, check if export was created
    """
    inputs = {'diff' : generate_diff_inputs()}
    mock_code = mock_code_factory(
        label='diff',
        data_dir_abspath=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calc_data'),
        entry_point=CALC_ENTRY_POINT,
        ignore_files=('_aiidasubmit.sh', 'file*')
    )
    inputs['diff']['code'] = mock_code

    res, node = run_get_node(DiffWorkChain, **inputs)
    res_diff = '''1,2c1
< Lorem ipsum dolor..
< 
---
> Please report to the ministry of silly walks.
'''
    assert node.is_finished_ok
    assert res['computed_diff'].get_content() == res_diff

    # now export cache
    savepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'caches/diff_workchain.tar.gz')
    if os.path.isfile(savepath):
        os.remove(savepath)
    export_cache(node, savepath=savepath)

    assert os.path.isfile(savepath)


def test_load_cache(load_cache, clear_database):
    """Basic test of the load cache fixture functionality, check if export is loaded"""
    #depends on previous test, maybe merge them?
    from aiida.orm.querybuilder import QueryBuilder

    cache_path = os.path.join(
                     os.path.dirname(os.path.abspath(__file__)),
                                    'caches/diff_workchain.tar.gz')
    # we check the number of nodes

    load_cache(cache_path)

    qb = QueryBuilder()
    qb.append(Node)
    n_nodes = len(qb.all())

    assert n_nodes == 9


@pytest.mark.timeout(60, method='thread')
def test_run_with_cache(aiida_profile, aiida_localhost, mock_code_factory, generate_diff_inputs, run_with_cache):
    """
    Basic test of the run with cache fixture functionality,
    should run workchain with cached calcjob
    """
    inputs = {'diff' : generate_diff_inputs()}
    mock_code = mock_code_factory(
        label='diff',
        data_dir_abspath=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calc_data'),
        entry_point=CALC_ENTRY_POINT,
        ignore_files=('_aiidasubmit.sh', 'file*')
    )
    inputs['diff']['code'] = mock_code
    #builder = DiffWorkChain.get_builder()
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'caches')
    #run_with_cache(builder=inputs, process_class=DiffWorkChain, data_dir=data_dir)
    #res, node = run_get_node(DiffWorkChain, **inputs)
    res, node = run_with_cache(builder=inputs, process_class=DiffWorkChain, data_dir=data_dir)

    res_diff = '''1,2c1
< Lorem ipsum dolor..
< 
---
> Please report to the ministry of silly walks.
'''
    assert node.is_finished_ok
    assert res['computed_diff'].get_content() == res_diff

    #Test if cache was used?
    diffjob = node.get_outgoing().get_node_by_label('CALL')
    cache_src = diffjob.get_cache_source()
    calc_hash_s = 'c36b0d984dada435a9002b4b999e9c335d94ce828e588eab3adafa1c24141f75'
    calc_hash = diffjob.get_hash()
    assert calc_hash == calc_hash_s
    assert cache_src is not None

