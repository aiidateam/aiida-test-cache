#!/usr/bin/env python

import os
import warnings

import setuptools
from setuptools.config import read_configuration

try:
    import fastentrypoints  # NOQA
except ImportError:
    warnings.warn(
        "The 'fastentrypoints' module could not be loaded. "
        "Installed console script will be slower."
    )

SETUP_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'setup.cfg')
SETUP_KWARGS = read_configuration(SETUP_CONFIG_PATH)
EXTRAS_REQUIRE = SETUP_KWARGS['options']['extras_require']
EXTRAS_REQUIRE['dev'] = (
    EXTRAS_REQUIRE["docs"] + EXTRAS_REQUIRE["testing"] + EXTRAS_REQUIRE["pre_commit"]
)
if __name__ == "__main__":
    setuptools.setup(extras_require=EXTRAS_REQUIRE)
