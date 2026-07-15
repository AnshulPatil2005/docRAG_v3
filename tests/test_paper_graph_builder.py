import pytest
from app.graph.paper_graph_builder import PaperGraphBuilder
from app.graph.ontology import OntologyValidator, NodeType, EdgeType

SAMPLE_METADATA = {
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani", "Noam Shazeer"],
    "year": 2017,
    "doi": "10.1234/nips.2017",
    "arxiv_id": "1706.03762",
}

SAMPLE_SECTIONS = [
    {"heading": "Abstract", "text": "We introduce the Transformer..."},
    {"heading": "Introduction", "text": "The Transformer is evaluated on WMT14..."},
]

SAMPLE_ENTITIES = [
    {"name": "Transformer", "type": "Method", "source_section": "Abstract", "confidence": 0.8},
    {"name": "Transformer", "type": "Method", "source_section": "Introduction", "confidence": 0.95}, # Duplicate with HIGHER confidence
    {"name": "RNN", "type": "Method", "source_section": "Introduction", "confidence": 0.9},
    {"name": "WMT14", "type": "Dataset", "source_section": "Introduction", "confidence": 0.9},
    {"name": "machine translation", "type": "Task", "source_section": "Abstract", "confidence": 0.9},
    {"name": "BLEU", "type": "Metric", "source_section": "Abstract", "confidence": 0.9},
    {"name": "We outperform state-of-the-art.", "type": "Claim", "source_section": "Abstract", "confidence": 0.7},
]

SAMPLE_RELATIONS = [
    {
        "source": "Transformer",
        "source_type": "Method",
        "relation": "IMPROVES_UPON",
        "target": "RNN",
        "target_type": "Method",
        "evidence": "Transformer outperforms traditional RNN models.",
        "confidence": 0.95,
    }
]

SAMPLE_CITATIONS = [
    {
        "title": "Sequence to Sequence Learning with Neural Networks",
        "authors": ["Ilya Sutskever"],
        "year": 2014,
        "doi": "10.1234/seq2seq",
    }
]


def test_paper_graph_builder_full_pipeline():
    builder = PaperGraphBuilder()
    graph = builder.build_graph(
        paper_id="att2017",
        paper_metadata=SAMPLE_METADATA,
        sections=SAMPLE_SECTIONS,
        entities=SAMPLE_ENTITIES,
        relations=SAMPLE_RELATIONS,
        citations=SAMPLE_CITATIONS,
    )

    assert "nodes" in graph
    assert "edges" in graph

    nodes = graph["nodes"]
    edges = graph["edges"]

    # 1. Check Main Paper Node
    paper_node = next((n for n in nodes if n["node_type"] == NodeType.PAPER.value and n["node_id"] == "paper_att2017"), None)
    assert paper_node is not None
    assert paper_node["name"] == "Attention Is All You Need"
    assert paper_node["properties"]["doi"] == "10.1234/nips.2017"
    assert paper_node["properties"]["arxiv_id"] == "1706.03762"

    # 2. Check Section Nodes and HAS_SECTION edges
    sec_nodes = [n for n in nodes if n["node_type"] == NodeType.SECTION.value]
    assert len(sec_nodes) == 2
    sec_headings = {n["name"] for n in sec_nodes}
    assert "Abstract" in sec_headings
    assert "Introduction" in sec_headings

    has_section_edges = [e for e in edges if e["edge_type"] == EdgeType.HAS_SECTION.value]
    assert len(has_section_edges) == 2
    for e in has_section_edges:
        assert e["source_id"] == "paper_att2017"
        assert e["target_id"].startswith("section_att2017_")

    # 3. Check Author Nodes and WRITTEN_BY edges
    author_nodes = [n for n in nodes if n["node_type"] == NodeType.AUTHOR.value]
    assert len(author_nodes) == 2
    author_names = {n["name"] for n in author_nodes}
    assert "Ashish Vaswani" in author_names
    assert "Noam Shazeer" in author_names

    written_by_edges = [e for e in edges if e["edge_type"] == EdgeType.WRITTEN_BY.value]
    assert len(written_by_edges) == 2

    # 4. Check Citation Paper Nodes and CITES edges
    citation_nodes = [n for n in nodes if n["node_type"] == NodeType.PAPER.value and n["node_id"] != "paper_att2017"]
    assert len(citation_nodes) == 1
    assert citation_nodes[0]["name"] == "Sequence to Sequence Learning with Neural Networks"
    assert citation_nodes[0]["properties"].get("is_citation") is True

    cites_edges = [e for e in edges if e["edge_type"] == EdgeType.CITES.value]
    assert len(cites_edges) == 1
    assert cites_edges[0]["source_id"] == "paper_att2017"
    assert cites_edges[0]["target_id"] == citation_nodes[0]["node_id"]


def test_entity_deduplication_highest_confidence():
    builder = PaperGraphBuilder()
    graph = builder.build_graph(
        paper_id="att2017",
        paper_metadata=SAMPLE_METADATA,
        sections=SAMPLE_SECTIONS,
        entities=SAMPLE_ENTITIES,
        relations=SAMPLE_RELATIONS,
        citations=SAMPLE_CITATIONS,
    )

    nodes = graph["nodes"]

    # "Transformer" (Method) was present twice, with confidence 0.8 and 0.95
    # Only ONE node should exist for it, and it should have the highest confidence (0.95)
    transformer_nodes = [n for n in nodes if n["name"] == "Transformer" and n["node_type"] == NodeType.METHOD.value]
    assert len(transformer_nodes) == 1
    assert transformer_nodes[0]["properties"]["confidence"] == 0.95
    # It should retain its source section for that highest confidence version
    assert transformer_nodes[0]["properties"]["source_section"] == "Introduction"


def test_claim_connection_to_section():
    builder = PaperGraphBuilder()
    graph = builder.build_graph(
        paper_id="att2017",
        paper_metadata=SAMPLE_METADATA,
        sections=SAMPLE_SECTIONS,
        entities=SAMPLE_ENTITIES,
        relations=SAMPLE_RELATIONS,
        citations=SAMPLE_CITATIONS,
    )

    nodes = graph["nodes"]
    edges = graph["edges"]

    claim_node = next((n for n in nodes if n["node_type"] == NodeType.CLAIM.value), None)
    assert claim_node is not None

    # Claim should be connected to the "Abstract" Section node via CONTAINS_CLAIM
    abstract_section = next((n for n in nodes if n["node_type"] == NodeType.SECTION.value and n["name"] == "Abstract"), None)
    assert abstract_section is not None

    contains_claim_edge = next((e for e in edges if e["edge_type"] == EdgeType.CONTAINS_CLAIM.value), None)
    assert contains_claim_edge is not None
    assert contains_claim_edge["source_id"] == abstract_section["node_id"]
    assert contains_claim_edge["target_id"] == claim_node["node_id"]


def test_relation_edges_connected_correctly():
    builder = PaperGraphBuilder()
    graph = builder.build_graph(
        paper_id="att2017",
        paper_metadata=SAMPLE_METADATA,
        sections=SAMPLE_SECTIONS,
        entities=SAMPLE_ENTITIES,
        relations=SAMPLE_RELATIONS,
        citations=SAMPLE_CITATIONS,
    )

    nodes = graph["nodes"]
    edges = graph["edges"]

    transformer_node = next((n for n in nodes if n["name"] == "Transformer"), None)
    rnn_node = next((n for n in nodes if n["name"] == "RNN"), None)
    assert transformer_node is not None
    assert rnn_node is not None

    improves_edge = next((e for e in edges if e["edge_type"] == EdgeType.IMPROVES_UPON.value), None)
    assert improves_edge is not None
    assert improves_edge["source_id"] == transformer_node["node_id"]
    assert improves_edge["target_id"] == rnn_node["node_id"]


def test_ontology_strict_validation():
    builder = PaperGraphBuilder()
    graph = builder.build_graph(
        paper_id="att2017",
        paper_metadata=SAMPLE_METADATA,
        sections=SAMPLE_SECTIONS,
        entities=SAMPLE_ENTITIES,
        relations=SAMPLE_RELATIONS,
        citations=SAMPLE_CITATIONS,
    )

    validator = OntologyValidator()

    for node in graph["nodes"]:
        assert validator.validate_node_type(node["node_type"])

    for edge in graph["edges"]:
        # Find source and target types
        source_node = next((n for n in graph["nodes"] if n["node_id"] == edge["source_id"]), None)
        target_node = next((n for n in graph["nodes"] if n["node_id"] == edge["target_id"]), None)

        assert source_node is not None
        assert target_node is not None

        assert validator.validate_edge(
            source_node["node_type"],
            edge["edge_type"],
            target_node["node_type"],
        )
