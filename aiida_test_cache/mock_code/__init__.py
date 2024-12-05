"""
Defines fixtures for mocking AiiDA codes, with caching at the level of
the executable.
"""
# ruff: noqa: F405

from ._fixtures import *  # noqa: F403
from ._hasher import InputHasher  # noqa: F401

# Note: This is necessary for the sphinx doc - otherwise it does not find aiida_test_cache.mock_code.mock_code_factory
__all__ = (
    "mock_code_factory",
    "mock_regenerate_test_data",
    "pytest_addoption",
    "testing_config",
    "testing_config_action",
)

# Load aiida's pytest fixtures
# For aiida-core>=2.6 we load new fixtures which use sqlite backend.
# WARNING: It's not clear what happens if the user later loads
# the old fixtures as well.
from aiida import __version__ as aiida_version
from pkg_resources import parse_version

if parse_version(aiida_version) >= parse_version('2.6.0'):
    aiida_core_fixtures = 'aiida.tools.pytest_fixtures'
else:
    aiida_core_fixtures = 'aiida.manage.tests.pytest_fixtures'
pytest_plugins = [aiida_core_fixtures]
