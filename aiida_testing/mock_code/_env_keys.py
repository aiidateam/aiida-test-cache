# -*- coding: utf-8 -*-
"""
Defines the environment variable names for the mock code execution.
"""

from enum import Enum


class EnvKeys(Enum):
    """
    An enum containing the environment variables defined for
    the mock code execution.
    """
    LOG_FILE = 'AIIDA_MOCK_LOG_FILE'
    LABEL = 'AIIDA_MOCK_LABEL'
    DATA_DIR = 'AIIDA_MOCK_DATA_DIR'
    EXECUTABLE_PATH = 'AIIDA_MOCK_EXECUTABLE_PATH'
    IGNORE_FILES = 'AIIDA_MOCK_IGNORE_FILES'
    IGNORE_PATHS = 'AIIDA_MOCK_IGNORE_PATHS'
    REGENERATE_DATA = 'AIIDA_MOCK_REGENERATE_DATA'
    FAIL_ON_MISSING = 'AIIDA_MOCK_FAIL_ON_MISSING'
