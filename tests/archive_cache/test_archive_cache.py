"""
Test basic usage of the mock code on examples using aiida-diff.
"""
import os
from pathlib import Path

import pytest
from aiida.engine import ToContext, WorkChain, run_get_node
from aiida.orm import Node
from aiida.orm.querybuilder import QueryBuilder
from aiida.plugins import CalculationFactory

from aiida_test_cache.archive_cache._utils import create_node_archive, load_node_archive

CALC_ENTRY_POINT = 'diff'
CWD = Path(__file__).parent

#### diff workchain for basic tests


class DiffWorkChain(WorkChain):
    """
    Very simple workchain which wraps a diff calculation for testing purposes
    """

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
        computed_diff = self.ctx.diff_calc.base.links.get_outgoing().get_node_by_label('diff')
        self.out('computed_diff', computed_diff)


@pytest.fixture(name='check_diff_workchain')
def check_diff_workchain_fixture():
    """Fixture to check the correct outputs/cachgin of the Diffworkchain
    in the tests in this file"""

    EXPECTED_DIFF = """1,2c1
< Lorem ipsum dolor..
< 
---
> Please report to the ministry of silly walks.
"""  # noqa: N806
    EXPECTED_HASH = '96535a026a714a51855ff788c6646badb7e35a4fb483526bf90474a9eaaa0847'  # noqa: N806

    def _check_diff_workchain(res, node, should_have_used_cache=True):

        assert node.is_finished_ok
        assert res['computed_diff'].get_content() == EXPECTED_DIFF

        #Test if cache was used?
        diffjob = node.base.links.get_outgoing().get_node_by_label('CALL')
        cache_src = diffjob.base.caching.get_cache_source()

        calc_hash = diffjob.base.caching.get_hash()
        assert calc_hash == EXPECTED_HASH, f'Hash mismatch. hashed objects: {diffjob.base.caching._get_objects_to_hash()}'

        #Make sure that the cache was used if it should have been
        if should_have_used_cache:
            assert cache_src is not None
        else:
            assert cache_src is None

    return _check_diff_workchain


#### tests


def test_create_node_archive(
    aiida_profile_clean, mock_code_factory, generate_diff_inputs, tmp_path
):
    """
    Basic test of the create node archive fixture functionality,
    runs diff workchain and creates archive, check if archive was created
    """

    inputs = {'diff': generate_diff_inputs()}
    mock_code = mock_code_factory(
        label='diff',
        data_dir_abspath=CWD / 'calc_data',
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

    archive_path = os.fspath(tmp_path / 'diff_workchain.tar.gz')
    create_node_archive(node, archive_path=archive_path)

    assert os.path.isfile(archive_path)


def test_load_node_archive(aiida_profile_clean, absolute_archive_path):
    """Basic test of the load node archive fixture functionality, check if archive is loaded"""

    full_archive_path = absolute_archive_path('diff_workchain.tar.gz')
    # we check the number of nodes
    load_node_archive(full_archive_path)

    qub = QueryBuilder()
    qub.append(Node)
    n_nodes = len(qub.all())

    assert n_nodes == 9


def test_mock_hash_codes(aiida_profile_clean, mock_code_factory, liberal_hash):
    """test if mock of _get_objects_to_hash works for Code and Calcs"""

    mock_code = mock_code_factory(
        label='diff',
        data_dir_abspath=CWD / 'calc_data',
        entry_point=CALC_ENTRY_POINT,
        ignore_paths=('_aiidasubmit.sh', 'file*')
    )
    objs = mock_code.base.caching._get_objects_to_hash()
    assert objs == [mock_code.base.attributes.get(key='input_plugin')]


@pytest.mark.parametrize(
    'archive_path', [CWD / 'caches/test_workchain.tar.gz', 'test_workchain.tar.gz']
)
def test_enable_archive_cache(
    archive_path, aiida_profile_clean, aiida_code_installed, generate_diff_inputs,
    enable_archive_cache, check_diff_workchain
):
    """
    Basic test of the enable_archive_cache fixture
    """

    inputs = {'diff': generate_diff_inputs()}
    diff_code = aiida_code_installed(filepath_executable='diff')
    diff_code.store()
    inputs['diff']['code'] = diff_code
    with enable_archive_cache(archive_path, calculation_class=CalculationFactory(CALC_ENTRY_POINT)):
        res, node = run_get_node(DiffWorkChain, **inputs)

    check_diff_workchain(res, node, should_have_used_cache=True)


def test_enable_archive_cache_non_existent(
    aiida_profile_clean, aiida_code_installed, generate_diff_inputs, enable_archive_cache,
    tmp_path_factory, check_diff_workchain
):
    """
    Test of the enable_archive_cache fixture that creation of the archive
    and overwriting of the archive works correctly
    """

    inputs = {'diff': generate_diff_inputs()}
    diff_code = aiida_code_installed(filepath_executable='diff')
    diff_code.store()
    inputs['diff']['code'] = diff_code

    #Absolute path to not pollute the test directory with test files
    archive_path = tmp_path_factory.mktemp(
        'enable-archive-cache-non-existent'
    ) / 'test_workchain.tar.gz'

    #Create archive that does not exist
    with enable_archive_cache(archive_path, calculation_class=CalculationFactory(CALC_ENTRY_POINT)):
        res, node = run_get_node(DiffWorkChain, **inputs)
    check_diff_workchain(res, node, should_have_used_cache=False)
