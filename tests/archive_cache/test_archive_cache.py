# -*- coding: utf-8 -*-
"""
Test basic usage of the mock code on examples using aiida-diff.
"""
# pylint: disable=unused-argument, protected-access

import os

from aiida.engine import run_get_node
from aiida.engine import WorkChain
from aiida.engine import ToContext
from aiida.orm import Node
from aiida.orm.querybuilder import QueryBuilder
from aiida.plugins import CalculationFactory

CALC_ENTRY_POINT = 'diff'

#### diff workchain for basic tests


class DiffWorkChain(WorkChain):
    """
    Very simple workchain which wraps a diff calculation for testing purposes
    """
    #pylint: disable=missing-function-docstring

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.expose_inputs(CalculationFactory(CALC_ENTRY_POINT), namespace='diff')
        spec.outline(
            cls.rundiff,
            cls.results,
        )
        spec.output('computed_diff')

    def rundiff(self):
        inputs = self.exposed_inputs(CalculationFactory(CALC_ENTRY_POINT), 'diff')
        running = self.submit(CalculationFactory(CALC_ENTRY_POINT), **inputs)

        return ToContext(diff_calc=running)

    def results(self):
        computed_diff = self.ctx.diff_calc.get_outgoing().get_node_by_label('diff')
        self.out('computed_diff', computed_diff)


#### tests


def test_create_node_archive(
    mock_code_factory, generate_diff_inputs, create_node_archive, clear_database, tmp_path
):
    """
    Basic test of the create node archive fixture functionality,
    runs diff workchain and creates archive, check if archive was created
    """
    inputs = {'diff': generate_diff_inputs()}
    mock_code = mock_code_factory(
        label='diff',
        data_dir_abspath=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calc_data'),
        entry_point=CALC_ENTRY_POINT,
        ignore_paths=('_aiidasubmit.sh', 'file*')
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

    archive_path = tmp_path / 'diff_workchain.tar.gz'
    create_node_archive(node, archive_path=archive_path)

    assert os.path.isfile(archive_path)


def test_load_node_archive(load_node_archive, clear_database):
    """Basic test of the load node archive fixture functionality, check if archive is loaded"""

    # we check the number of nodes
    load_node_archive('diff_workchain.tar.gz')

    qub = QueryBuilder()
    qub.append(Node)
    n_nodes = len(qub.all())

    assert n_nodes == 9


def test_mock_hash_codes(mock_code_factory, clear_database, liberal_hash):
    """test if mock of _get_objects_to_hash works for Code and Calcs"""

    mock_code = mock_code_factory(
        label='diff',
        data_dir_abspath=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calc_data'),
        entry_point=CALC_ENTRY_POINT,
        ignore_paths=('_aiidasubmit.sh', 'file*')
    )
    objs = mock_code._get_objects_to_hash()
    assert objs == [mock_code.get_attribute(key='input_plugin')]  #, mock_code.get_computer_name()]


def test_run_with_cache(
    aiida_local_code_factory,  #mock_code_factory,
    generate_diff_inputs,
    run_with_cache,
    clear_database
):
    """
    Basic test of the run with cache fixture functionality,
    should run workchain with cached calcjob
    """
    inputs = {'diff': generate_diff_inputs()}
    diff_code = aiida_local_code_factory(executable='diff', entry_point='diff')
    diff_code.store()
    inputs['diff']['code'] = diff_code
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'caches')

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
    print(diffjob._get_objects_to_hash())  # in case of failure to compare
    calc_hash_s = '96535a026a714a51855ff788c6646badb7e35a4fb483526bf90474a9eaaa0847'
    calc_hash = diffjob.get_hash()
    assert calc_hash == calc_hash_s
    assert cache_src is not None  # Hint: maybe rerun, if the export was just created


def test_enable_archive_cache(
    aiida_local_code_factory, generate_diff_inputs, enable_archive_cache, clear_database
):
    """
    Basic test of the enable_archive_cache fixture
    """

    inputs = {'diff': generate_diff_inputs()}
    diff_code = aiida_local_code_factory(executable='diff', entry_point='diff')
    diff_code.store()
    inputs['diff']['code'] = diff_code
    archive_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'caches/test_workchain.tar.gz'
    )
    with enable_archive_cache(archive_path, calculation_class=CalculationFactory(CALC_ENTRY_POINT)):
        res, node = run_get_node(DiffWorkChain, **inputs)

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
    print(diffjob._get_objects_to_hash())  # in case of failure to compare
    calc_hash_s = '96535a026a714a51855ff788c6646badb7e35a4fb483526bf90474a9eaaa0847'
    calc_hash = diffjob.get_hash()
    assert calc_hash == calc_hash_s
    assert cache_src is not None  # Hint: maybe rerun, if the export was just created
