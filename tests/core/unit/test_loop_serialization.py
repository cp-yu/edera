import pytest
from edera_core.service_common import dag_node_payload, graph_dag_payload


def test_loop_serialization_roundtrip():
    node = {
        "id": "test-node",
        "type": "rss-fetcher",
        "loop": {"mode": "parallel", "count": 3, "until": "output.done == True"},
        "resource": "test_resource",
        "config": {}
    }

    payload = dag_node_payload(node)

    assert payload["loop"] == {"mode": "parallel", "count": 3, "until": "output.done == True"}
    assert payload["resource"] == "test_resource"


def test_loop_serialization_without_loop():
    node = {
        "id": "test-node",
        "type": "rss-fetcher",
        "config": {}
    }

    payload = dag_node_payload(node)

    assert "loop" not in payload
    assert "resource" not in payload


def test_graph_payload_with_loop():
    graph = {
        "nodes": [
            {
                "id": "loop-node",
                "type": "rss-fetcher",
                "loop": {"mode": "serial", "count": 2},
                "resource": "my_resource",
                "config": {}
            }
        ],
        "edges": []
    }

    payload = graph_dag_payload("test-dag", graph)

    assert payload["nodes"][0]["loop"]["mode"] == "serial"
    assert payload["nodes"][0]["loop"]["count"] == 2
    assert payload["nodes"][0]["resource"] == "my_resource"
