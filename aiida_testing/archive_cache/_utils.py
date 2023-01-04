"""
Defines helper functions for the archive_cache pytest fixtures
"""
import typing as ty

import pytest

from aiida.orm import ProcessNode, QueryBuilder, Node

__all__ = ('rehash_processes', 'monkeypatch_hash_objects')


def rehash_processes() -> None:
    """
    Recompute the hashes for all ProcessNodes
    """
    qub = QueryBuilder()
    qub.append(ProcessNode)
    to_hash = qub.all()
    for node1 in to_hash:
        node1[0].rehash()


def monkeypatch_hash_objects(
    monkeypatch: pytest.MonkeyPatch, node_class: ty.Type[Node], hash_objects_func: ty.Callable
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
    #pylint: disable=too-few-public-methods,protected-access

    try:
        monkeypatch.setattr(node_class, "_get_objects_to_hash", hash_objects_func)
    except AttributeError:
        node_caching_class = node_class._CLS_NODE_CACHING

        class MockNodeCaching(node_caching_class):  #type: ignore
            """
            NodeCaching subclass with stripped down _get_objects_to_hash method
            """

            def _get_objects_to_hash(self):
                return hash_objects_func(self)

        monkeypatch.setattr(node_class, "_CLS_NODE_CACHING", MockNodeCaching)


def get_node_from_hash_objects_caller(caller: ty.Any) -> Node:
    """
    Get the actual node instance from the class calling the
    _get_objects_to_hash method

    :param caller: object holding _get_objects_to_hash
    """
    try:
        #Case for AiiDA 2.0: The class holding the _get_objects_to_hash method
        #is the NodeCaching class not the actual node
        return caller._node  #type: ignore[no-any-return] #pylint: disable=protected-access
    except AttributeError:
        return caller  #type: ignore[no-any-return]
