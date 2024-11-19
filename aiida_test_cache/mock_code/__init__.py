"""
Defines fixtures for mocking AiiDA codes, with caching at the level of
the executable.
"""

from ._hasher import InputHasher
from ._fixtures import (
    pytest_addoption,
    testing_config_action,
    mock_regenerate_test_data,
    testing_config,
    mock_code_factory,
)

# Note: This is necessary for the sphinx doc - otherwise it does not find aiida_test_cache.mock_code.mock_code_factory
__all__ = (
    "pytest_addoption",
    "testing_config_action",
    "mock_regenerate_test_data",
    "testing_config",
    "mock_code_factory",
)

# Load aiida's pytest fixtures
try:
    # These new fixtures which use sqlite backend, introduced in aiida v2.6
    # NOTE: It's not clear what happens if the user than activates
    # the old fixtures as well.
    import aiida.tools.pytest_fixtures  # type: ignore[import-not-found]
except ImportError:
    aiida_core_fixtures = 'aiida.manage.tests.pytest_fixtures'
else:
    aiida_core_fixtures = 'aiida.tools.pytest_fixtures'
pytest_plugins = [aiida_core_fixtures]
