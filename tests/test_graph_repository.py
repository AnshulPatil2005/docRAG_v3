"""Tests for GraphRepository (Phase 8.2), focused on get_paper_graph."""

from unittest.mock import MagicMock

import pytest

from app.storage.graph_repository import GraphRepository


def _make_repo(rows):
    client = MagicMock()
    client.query.return_value = rows
    return GraphRepository(client), client


class TestFindRealPaperId:
    def test_finds_by_doi(self):
        repo, client = _make_repo([{"pid": "real123"}])
        assert repo.find_real_paper_id(doi="10.1234/x") == "real123"
        cypher = client.query.call_args[0][0]
        assert "is_stub: False" in cypher
        assert "doi:" in cypher

    def test_finds_by_arxiv_id(self):
        repo, client = _make_repo([{"pid": "real456"}])
        assert repo.find_real_paper_id(arxiv_id="1706.03762") == "real456"

    def test_returns_none_when_not_found(self):
        repo, client = _make_repo([])
        assert repo.find_real_paper_id(arxiv_id="1706.03762") is None

    def test_returns_none_when_neither_identifier_given(self):
        repo, client = _make_repo([{"pid": "real123"}])
        assert repo.find_real_paper_id() is None
        client.query.assert_not_called()


class TestGetCitationGraph:
    def test_returns_all_papers_and_cites_edges(self):
        client = MagicMock()
        client.query.side_effect = [
            [
                {"paper_id": "p1", "title": "Paper One", "name": "Paper One", "year": 2021, "is_stub": False},
                {"paper_id": "p2", "title": "Paper Two", "name": "Paper Two", "year": 2022, "is_stub": False},
                {"paper_id": "arxiv_1706.03762", "title": None, "name": "Attention Is All You Need", "year": None, "is_stub": True},
            ],
            [
                {"source": "p2", "target": "p1"},
                {"source": "p1", "target": "arxiv_1706.03762"},
            ],
        ]
        repo = GraphRepository(client)

        graph = repo.get_citation_graph()

        assert len(graph["papers"]) == 3
        assert len(graph["edges"]) == 2
        assert graph["edges"][0] == {"source": "p2", "target": "p1"}
        stub = next(p for p in graph["papers"] if p["paper_id"] == "arxiv_1706.03762")
        assert stub["is_stub"] is True

    def test_empty_graph(self):
        client = MagicMock()
        client.query.side_effect = [[], []]
        repo = GraphRepository(client)

        graph = repo.get_citation_graph()

        assert graph == {"papers": [], "edges": []}


class TestGetPaperGraph:
    def test_returns_empty_dict_when_paper_missing(self):
        repo, client = _make_repo([])
        assert repo.get_paper_graph("missing") == {}

    def test_returns_empty_dict_when_paper_node_is_null(self):
        repo, client = _make_repo([{"p": None}])
        assert repo.get_paper_graph("missing") == {}

    def test_aggregates_all_relationships_not_just_first_row(self):
        rows = [
            {
                "p": {"node_id": "p1", "paper_id": "p1", "title": "My Paper"}, "p_labels": ["Paper"],
                "r_type": "HAS_SECTION", "r_props": {},
                "r_start": {"node_id": "p1", "paper_id": "p1", "title": "My Paper"}, "r_start_labels": ["Paper"],
                "r_end": {"node_id": "sec1", "section_id": "sec1", "heading": "Intro"}, "r_end_labels": ["Section"],
            },
            {
                "p": {"node_id": "p1", "paper_id": "p1", "title": "My Paper"}, "p_labels": ["Paper"],
                "r_type": "MENTIONS", "r_props": {"confidence": 1.0},
                "r_start": {"node_id": "p1", "paper_id": "p1", "title": "My Paper"}, "r_start_labels": ["Paper"],
                "r_end": {"node_id": "Transformer", "name": "Transformer", "evidence": "..."}, "r_end_labels": ["Method"],
            },
        ]
        repo, client = _make_repo(rows)

        graph = repo.get_paper_graph("p1")

        node_ids = {n["id"] for n in graph["nodes"]}
        assert node_ids == {"p1", "sec1", "Transformer"}
        assert len(graph["edges"]) == 2

        edge_types = {e["type"] for e in graph["edges"]}
        assert edge_types == {"HAS_SECTION", "MENTIONS"}

        mentions_edge = next(e for e in graph["edges"] if e["type"] == "MENTIONS")
        assert mentions_edge["source"] == "p1"
        assert mentions_edge["source_type"] == "Paper"
        assert mentions_edge["target"] == "Transformer"
        assert mentions_edge["target_type"] == "Method"

    def test_paper_with_no_relationships_returns_lone_node(self):
        rows = [{
            "p": {"node_id": "p1", "paper_id": "p1", "title": "Lonely Paper"}, "p_labels": ["Paper"],
            "r_type": None, "r_props": None,
            "r_start": None, "r_start_labels": None,
            "r_end": None, "r_end_labels": None,
        }]
        repo, client = _make_repo(rows)

        graph = repo.get_paper_graph("p1")

        assert [n["id"] for n in graph["nodes"]] == ["p1"]
        assert graph["edges"] == []

    def test_nodes_deduplicated_across_multiple_edges(self):
        # Two different sections both linked to the paper -- paper node
        # must only appear once in the result.
        rows = [
            {
                "p": {"node_id": "p1", "paper_id": "p1"}, "p_labels": ["Paper"],
                "r_type": "HAS_SECTION", "r_props": {},
                "r_start": {"node_id": "p1", "paper_id": "p1"}, "r_start_labels": ["Paper"],
                "r_end": {"node_id": "sec1", "section_id": "sec1", "heading": "Intro"}, "r_end_labels": ["Section"],
            },
            {
                "p": {"node_id": "p1", "paper_id": "p1"}, "p_labels": ["Paper"],
                "r_type": "HAS_SECTION", "r_props": {},
                "r_start": {"node_id": "p1", "paper_id": "p1"}, "r_start_labels": ["Paper"],
                "r_end": {"node_id": "sec2", "section_id": "sec2", "heading": "Methods"}, "r_end_labels": ["Section"],
            },
        ]
        repo, client = _make_repo(rows)

        graph = repo.get_paper_graph("p1")

        assert sorted(n["id"] for n in graph["nodes"]) == ["p1", "sec1", "sec2"]
