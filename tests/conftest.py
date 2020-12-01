# -*- coding: utf-8 -*-
"""
Configuration file for pytest tests of aiida-testing.
"""
pytest_plugins = ['aiida.manage.tests.pytest_fixtures', 'aiida_testing.mock_code']  # pylint: disable=invalid-name
