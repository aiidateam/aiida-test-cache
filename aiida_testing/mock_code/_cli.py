# -*- coding: utf-8 -*-
"""Defines the fallback executable that is used in a Code when no other
executable is configured.
"""

import sys


def run():
    """Dummy executable that is passed to a Code when no config is set.
    """
    sys.exit("No executable specified in the aiida-testing config, and no existing result found.")
