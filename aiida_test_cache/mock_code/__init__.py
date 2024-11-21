"""
Defines fixtures for mocking AiiDA codes, with caching at the level of
the executable.
"""

from ._fixtures import (
    mock_code_factory,
    mock_regenerate_test_data,
    pytest_addoption,
    testing_config,
    testing_config_action,
)
from ._hasher import InputHasher

# Note: This is necessary for the sphinx doc - otherwise it does not find aiida_test_cache.mock_code.mock_code_factory
__all__ = (
    "pytest_addoption",
    "testing_config_action",
    "mock_regenerate_test_data",
    "testing_config",
    "mock_code_factory",
    "InputHasher",
)

# ensure aiida's pytest plugin is loaded, which we rely on
pytest_plugins = ['aiida.manage.tests.pytest_fixtures']
