[![Build Status](https://github.com/aiidateam/aiida-testing/workflows/ci/badge.svg)](https://github.com/aiidateam/aiida-testing/actions)
[![Docs status](https://readthedocs.org/projects/aiida-testing/badge)](http://aiida-testing.readthedocs.io/)
[![PyPI version](https://badge.fury.io/py/aiida-testing.svg)](https://badge.fury.io/py/aiida-testing)
[![GitHub license](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/aiidateam/aiida-testing/blob/main/LICENSE)

# aiida-testing

A pytest plugin to simplify testing of AiiDA plugins. This package implements two ways of running an AiiDA calculation in tests:
- `mock_code`: Implements a caching layer at the level of the executable called by an AiiDA calculation. This tests the input generation and output parsing, which is useful when testing calculation and parser plugins.
- `export_cache`: Implements an automatic export / import of the AiiDA database, to enable AiiDA - level caching in tests. This circumvents the input generation / output parsing, making it suitable for testing higher-level workflows. 

For more information, see the [documentation](http://aiida-testing.readthedocs.io/).
