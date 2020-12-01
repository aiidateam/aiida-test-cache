# -*- coding: utf-8 -*-
"""
Defines the environment variable names for the mock code execution.
"""

from enum import Enum


class CodeExtraKeys(Enum):
    """
    An enum containing the keys to be used in the `Code` extras.
    """
    LABEL = 'AIIDA_MOCK_LABEL'
    DATA_DIR = 'AIIDA_MOCK_DATA_DIR'
    EXECUTABLE_PATH = 'AIIDA_MOCK_EXECUTABLE_PATH'
    IGNORE_FILES = 'AIIDA_MOCK_IGNORE_FILES'
    IGNORE_PATHS = 'AIIDA_MOCK_IGNORE_PATHS'
    REGENERATE_DATA = 'AIIDA_MOCK_REGENERATE_DATA'


class CalculationExtraKeys(Enum):
    """
    An enum containing the keys to be used in the `Calculation` extras.
    """
    NEEDS_COPY_TO_RES_DIR = 'AIIDA_MOCK_NEEDS_COPY_TO_RES_DIR'
    RES_DIR = 'AIIDA_MOCK_RES_DIR'
