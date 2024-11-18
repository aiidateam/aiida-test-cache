# -*- coding: utf-8 -*-
"""
Helpers for managing the ``.aiida-testing-config.yml`` configuration file.
"""

import pathlib
import typing as ty
import collections
from enum import Enum
from voluptuous import Schema

import yaml

CONFIG_FILE_NAME = '.aiida-testing-config.yml'


class ConfigActions(Enum):
    """
    An enum containing the actions to perform on the config file.
    """
    READ = 'read'
    GENERATE = 'generate'
    REQUIRE = 'require'


class Config(collections.abc.MutableMapping):
    """Configuration of aiida-test-cache package."""

    schema = Schema({
        'mock_code': Schema({str: str}),
        'archive_cache': {
            'default_cache_dir': str,
            'ignore': {
                'calcjob_inputs': [str],
                'calcjob_attributes': [str],
                'node_attributes': Schema({str: [str]})
            }
        }
    })

    def __init__(self, config=None, file_path=None):
        self._dict = config or {}
        self._file_path = file_path or pathlib.Path().cwd() / CONFIG_FILE_NAME
        self.validate()

    def validate(self):
        """Validate configuration dictionary."""
        return self.schema(self._dict)

    @classmethod
    def from_file(cls) -> 'Config':
        """
        Parses the configuration file ``.aiida-testing-config.yml``.

        The file is searched in the current working directory and all its parent
        directories.
        """
        cwd = pathlib.Path().cwd()
        config: ty.Dict[str, str]
        for dir_path in [cwd, *cwd.parents]:
            config_file_path = dir_path / CONFIG_FILE_NAME
            if config_file_path.exists():
                with open(config_file_path, encoding='utf8') as config_file:
                    config = yaml.load(config_file, Loader=yaml.SafeLoader)
                    break
        else:
            config = {}

        return cls(config, file_path=config_file_path)

    def to_file(self):
        """Write configuration to file in yaml format.

        Writes to current working directory.

        :param handle: File handle to write config file to.
        """
        with open(self.file_path, 'w', encoding='utf8') as handle:
            yaml.dump(self._dict, handle, Dumper=yaml.SafeDumper)

    @property
    def file_path(self):
        """
        Path to the configuration file
        """
        return self._file_path

    def __getitem__(self, item):
        return self._dict.__getitem__(item)

    def __setitem__(self, key, value):
        return self._dict.__setitem__(key, value)

    def __delitem__(self, key):
        return self._dict.__delitem__(key)

    def __iter__(self):
        return self._dict.__iter__()

    def __len__(self):
        return self._dict.__len__()
