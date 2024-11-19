[![Build Status](https://github.com/aiidateam/aiida-test-cache/actions/workflows/ci.yml/badge.svg)](https://github.com/aiidateam/aiida-test-cache/actions)
[![Docs status](https://readthedocs.org/projects/aiida-testing/badge)](https://aiida-testing.readthedocs.io/)
[![PyPI version](https://badge.fury.io/py/aiida-test-cache.svg)](https://badge.fury.io/py/aiida-test-cache)
[![GitHub license](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/aiidateam/aiida-test-cache/blob/main/LICENSE)

# aiida-test-cache

A pytest plugin to simplify testing of AiiDA plugins. This package implements two ways of running an AiiDA calculation in tests:
- `mock_code`: Implements a caching layer at the level of the executable called by an AiiDA calculation. This tests the input generation and output parsing, which is useful when testing calculation and parser plugins.
- `archive_cache`: Implements an automatic archive creation and loading, to enable AiiDA - level caching in tests. This circumvents the input generation / output parsing, making it suitable for testing higher-level workflows. 

For more information, see the [documentation](https://aiida-testing.readthedocs.io/).
