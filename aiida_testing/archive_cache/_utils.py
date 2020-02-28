"""
Defines helper functions for the archive_cache pytest fixtures
"""
import typing as ty
import hashlib

import pytest

from aiida.orm import ProcessNode, QueryBuilder, Code, Node
from aiida.engine import ProcessBuilderNamespace
from aiida.common.hashing import make_hash

__all__ = ('rehash_processes', 'unnest_dict', 'get_hash_process', 'monkeypatch_hash_objects')


def rehash_processes() -> None:
    """
    Recompute the hashes for all ProcessNodes
    """
    qub = QueryBuilder()
    qub.append(ProcessNode)
    to_hash = qub.all()
    for node1 in to_hash:
        node1[0].rehash()


def unnest_dict(nested_dict: ty.Union[dict, ProcessBuilderNamespace]) -> dict:  #type: ignore
    """
    Returns a simple dictionary from a possible arbitrary nested dictionary
    or Aiida ProcessBuilderNamespace by adding keys in dot notation, recursively
    """
    new_dict = {}
    for key, val in nested_dict.items():
        if isinstance(val, (dict, ProcessBuilderNamespace)):
            unval = unnest_dict(val)  #recursive!
            for key2, val2 in unval.items():
                new_dict[f'{key}.{key2}'] = val2
        else:
            new_dict[str(key)] = val  #type: ignore
    return new_dict


def get_hash_process( #type: ignore
    builder: ty.Union[dict, ProcessBuilderNamespace], input_nodes: ty.Union[list, None] = None
):
    """Create a hash from a builder/dictionary of inputs"""

    if input_nodes is None:
        input_nodes = []

    # hashing the builder
    # currently workchains are not hashed in AiiDA so we create a hash for the filename
    unnest_builder = unnest_dict(builder)
    md5sum = hashlib.md5()
    for _, val in sorted(unnest_builder.items()):  # pylint: disable=unused-variable
        if isinstance(val, Code):
            continue  # we do not include the code in the hash, might be mocked
            #TODO include the code to some extent #pylint: disable=fixme
        if isinstance(val, Node):
            if not val.is_stored:
                val.store()
            val_hash = val.get_hash()  # only works if nodes are stored!
            input_nodes.append(val)
        else:
            val_hash = make_hash(val)
        md5sum.update(val_hash.encode())
    bui_hash = md5sum.hexdigest()

    return bui_hash, input_nodes


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
