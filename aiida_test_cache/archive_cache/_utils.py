"""
Defines helper functions for the archive_cache pytest fixtures
"""
import os
import pathlib
import typing as ty
from functools import partial

import pytest
from aiida.cmdline.utils.echo import echo_warning
from aiida.orm import Node, ProcessNode, QueryBuilder
from aiida.tools.archive import create_archive, import_archive

__all__ = ('monkeypatch_hash_objects', 'rehash_processes')


def rehash_processes() -> None:
    """
    Recompute the hashes for all ProcessNodes
    """
    qub = QueryBuilder()
    qub.append(ProcessNode)
    to_hash = qub.all()
    for node1 in to_hash:
        node1[0].base.caching.rehash()


def monkeypatch_hash_objects(
    monkeypatch: pytest.MonkeyPatch, node_class: type[Node], hash_objects_func: ty.Callable
) -> None:
    """
    Monkeypatch the _get_objects_to_hash method in aiida-core for the given node class

    :param monkeypatch: monkeypatch fixture of pytest
    :param node_class: Node class to monkeypatch
    :param hash_objects_func: function, which should be called instead of the
                              `_get_objects_to_hash` method

    .. note::

        For AiiDA 2.0 it is not enough to monkeypatch the methods on the
        respective classes since the caching methods are separated from the
        node classes and are available through a cached property on a completely
        spearate Caching class. Therefore to have the same effect a subclass of the
        Caching class with the modified methods is created and the Node classes are
        monkeypatched on the Nodes, i.e. the _CLS_NODE_CACHING attribute

    """
    try:
        monkeypatch.setattr(node_class, "_get_objects_to_hash", hash_objects_func)
    except AttributeError:
        node_caching_class = node_class._CLS_NODE_CACHING

        class MockNodeCaching(node_caching_class):  #type: ignore
            """
            NodeCaching subclass with stripped down _get_objects_to_hash method
            """

            # Compatibility with aiida-core < 2.6
            # In https://github.com/aiidateam/aiida-core/pull/6323
            def _get_objects_to_hash(self):
                return self.get_objects_to_hash()

            def get_objects_to_hash(self):
                return hash_objects_func(self)

            # Compatibility with aiida-core < 2.6
            # https://github.com/aiidateam/aiida-core/pull/6347
            def compute_hash(self):
                try:
                    return super().compute_hash()
                except AttributeError:
                    return super().get_hash()

        monkeypatch.setattr(node_class, "_CLS_NODE_CACHING", MockNodeCaching)


def get_node_from_hash_objects_caller(caller: ty.Any) -> Node:
    """
    Get the actual node instance from the class calling the
    _get_objects_to_hash method

    :param caller: object holding _get_objects_to_hash
    """
    #Case for AiiDA 2.0: The class holding the _get_objects_to_hash method
    #is the NodeCaching class not the actual node
    return caller._node  #type: ignore[no-any-return]


import_archive = partial(import_archive, merge_extras=('n', 'c', 'u'), import_new_extras=True)


def import_with_migrate(
    archive_path: ty.Union[str, pathlib.Path],
    *args: ty.Any,
    forbid_migration: bool = False,
    **kwargs: ty.Any,
) -> None:
    """
    Import AiiDA Archive. If the version is incompatible
    try to migrate the archive if --archive-cache-forbid-migration option is not specified
    """
    from aiida.common.exceptions import IncompatibleStorageSchema
    from aiida.tools.archive import get_format

    try:
        import_archive(archive_path, *args, **kwargs)
    except IncompatibleStorageSchema:
        if not forbid_migration:
            echo_warning(f'incompatible version detected for {archive_path}, trying migration')
            archive_format = get_format()
            version = archive_format.latest_version
            archive_format.migrate(archive_path, archive_path, version, force=True, compression=6)
            import_archive(archive_path, *args, **kwargs)
        else:
            raise


def load_node_archive(archive_path: str, forbid_migration: bool = False) -> None:
    """
    Function to import an AiiDA graph

    :param archive_path: absolute path to the archive to create (created by absolute_archive_path)
    :raises : FileNotFoundError, if import file is non existent
    """
    if os.path.exists(archive_path) and os.path.isfile(archive_path):
        # import cache, also import extras
        import_with_migrate(archive_path, forbid_migration=forbid_migration)
    else:
        raise FileNotFoundError(f"File: {archive_path} to be imported does not exist.")

    # need to rehash after import, otherwise cashing does not work
    # for this we rehash all process nodes
    rehash_processes()


def create_node_archive(
    nodes: ty.Union[Node, list[Node]], archive_path: str, overwrite: bool = True
) -> None:
    """
    Function to export an AiiDA graph from a given node.
    Uses the export functionalities of aiida-core

    :param node: AiiDA node or list of nodes from whose graph the archive should be created
    :param archive_path: absolute path to the archive to create (created by absolute_archive_path)
    :param overwrite: bool, default=True, if True any existing export is overwritten
    """

    # rehash before the export, since what goes in the hash is monkeypatched
    rehash_processes()

    if isinstance(nodes, list):
        to_export = nodes
    else:
        to_export = [nodes]

    create_archive(
        to_export, filename=archive_path, overwrite=overwrite, include_comments=True
    )  # extras are automatically included
