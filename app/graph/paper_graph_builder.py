"""
Paper Graph Builder module for Phase 7.

Combines paper metadata, sections, extracted entities, relations, and citations
into a single ontology-compliant, deduplicated graph representation.
"""

import hashlib
from typing import Any, Dict, List, Set, Tuple, Optional
import structlog

from app.graph.ontology import Node, Edge, NodeType, EdgeType, OntologyValidator

logger = structlog.get_logger()


class PaperGraphBuilder:
    """
    Builds a unified, ontology-valid local graph for a single research paper.

    EDUCATIONAL EXPLANATION:
    The Paper Graph Builder connects all preceding phases (Ontology, Parser, Citation,
    Entity, and Relation Extraction) into a single unified Data Structure.

    This structured graph representation is what will be stored in Neo4j (Phase 8),
    and is used to generate semantic vector representations in Qdrant (Phase 9).

    Deduplication Policy:
    Entities extracted from different sentences might refer to the same node (e.g.,
    "Transformer" in Section 1 and Section 2). We deduplicate these by normalized
    name, type, and paper_id, keeping the node representation with the highest confidence
    or richer evidence.
    """

    def __init__(self):
        self.validator = OntologyValidator()

    def build_graph(
        self,
        paper_id: str,
        paper_metadata: Dict[str, Any],
        sections: List[Dict[str, str]],
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Builds a single paper graph representation.

        Args:
            paper_id: Unique identifier for the main paper
            paper_metadata: Dict containing title, authors, etc.
            sections: List of parsed section dicts (heading, text)
            entities: List of extracted entity dicts
            relations: List of extracted relation dicts
            citations: List of normalized citation dicts

        Returns:
            Dict containing 'nodes' and 'edges' lists.
        """
        logger.info("building_paper_graph", paper_id=paper_id)

        nodes_map: Dict[str, Node] = {}
        edges: List[Edge] = []

        # 1. Create the Main Paper Node
        title = paper_metadata.get("title") or "Unknown Title"
        main_paper_node = Node(
            node_id=f"paper_{paper_id}",
            node_type=NodeType.PAPER.value,
            name=title,
            paper_id=paper_id,
            properties={
                "doi": paper_metadata.get("doi") or "",
                "arxiv_id": paper_metadata.get("arxiv_id") or "",
                "year": paper_metadata.get("year") or 0,
            }
        )
        nodes_map[main_paper_node.node_id] = main_paper_node

        # 2. Add Section Nodes & Link to Paper
        section_id_map: Dict[str, str] = {} # maps heading to section_id
        for sec in sections:
            heading = sec.get("heading") or "Unknown"
            sec_hash = self._hash_str(heading)
            sec_node_id = f"section_{paper_id}_{sec_hash}"

            section_node = Node(
                node_id=sec_node_id,
                node_type=NodeType.SECTION.value,
                name=heading,
                paper_id=paper_id,
                properties={"text_preview": (sec.get("text") or "")[:200]}
            )
            nodes_map[section_node.node_id] = section_node
            section_id_map[heading.lower()] = sec_node_id

            # Create Paper -> HAS_SECTION -> Section edge
            edges.append(Edge(
                source_id=main_paper_node.node_id,
                source_type=NodeType.PAPER.value,
                edge_type=EdgeType.HAS_SECTION.value,
                target_id=section_node.node_id,
                target_type=NodeType.SECTION.value,
            ))

        # 3. Add Author Nodes & Link to Paper
        authors = paper_metadata.get("authors") or []
        for author_name in authors:
            if not author_name or not author_name.strip():
                continue
            author_hash = self._hash_str(author_name)
            author_node_id = f"author_{author_hash}"

            # Check if Author node already instantiated
            if author_node_id not in nodes_map:
                nodes_map[author_node_id] = Node(
                    node_id=author_node_id,
                    node_type=NodeType.AUTHOR.value,
                    name=author_name,
                    paper_id=paper_id,
                )

            # Create Paper -> WRITTEN_BY -> Author edge
            edges.append(Edge(
                source_id=main_paper_node.node_id,
                source_type=NodeType.PAPER.value,
                edge_type=EdgeType.WRITTEN_BY.value,
                target_id=author_node_id,
                target_type=NodeType.AUTHOR.value,
            ))

        # 4. Add Citations as Paper Nodes & Link
        for cite in citations:
            cite_title = cite.get("title") or "Unknown Citation Title"
            cite_hash = self._hash_str(cite_title)
            cite_node_id = f"paper_cite_{cite_hash}"

            # Avoid overwriting main paper node if self-citation
            if cite_node_id not in nodes_map:
                nodes_map[cite_node_id] = Node(
                    node_id=cite_node_id,
                    node_type=NodeType.PAPER.value,
                    name=cite_title,
                    paper_id=paper_id,
                    properties={
                        "doi": cite.get("doi") or "",
                        "arxiv_id": cite.get("arxiv_id") or "",
                        "year": cite.get("year") or 0,
                        "authors": cite.get("authors") or [],
                        "is_citation": True,
                    }
                )

            # Create Paper -> CITES -> Paper (Citation) edge
            edges.append(Edge(
                source_id=main_paper_node.node_id,
                source_type=NodeType.PAPER.value,
                edge_type=EdgeType.CITES.value,
                target_id=cite_node_id,
                target_type=NodeType.PAPER.value,
            ))

        # 5. Process & Deduplicate Extracted Entities (Methods, Datasets, Tasks, Metrics, Claims, Experiments)
        # Deduplication Policy: Keep entity with highest confidence score.
        dedup_entities: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for ent in entities:
            name = ent.get("name")
            ent_type = ent.get("type")
            if not name or not ent_type:
                continue

            key = (ent_type.lower(), name.lower().strip())
            confidence = float(ent.get("confidence") if ent.get("confidence") is not None else 1.0)
            ent["confidence_parsed"] = confidence

            if key not in dedup_entities:
                dedup_entities[key] = ent
            else:
                existing = dedup_entities[key]
                if confidence > existing["confidence_parsed"]:
                    dedup_entities[key] = ent

        # Build nodes and map entity keys to unique generated node_ids
        entity_key_to_id: Dict[Tuple[str, str], str] = {}
        for (ent_type, ent_name), ent in dedup_entities.items():
            node_type_val = ent["type"]
            node_id = self._generate_node_id(node_type_val, paper_id, ent["name"])
            entity_key_to_id[(node_type_val.lower(), ent["name"].lower())] = node_id

            node_properties = {
                "evidence": ent.get("evidence") or "",
                "source_section": ent.get("source_section") or "Unknown",
                "confidence": ent["confidence_parsed"],
            }

            nodes_map[node_id] = Node(
                node_id=node_id,
                node_type=node_type_val,
                name=ent["name"],
                paper_id=paper_id,
                properties=node_properties,
            )

            # Connect Claim node to its parent Section node via CONTAINS_CLAIM
            if node_type_val == NodeType.CLAIM.value:
                sec_heading = ent.get("source_section") or "Unknown"
                sec_node_id = section_id_map.get(sec_heading.lower())
                if sec_node_id:
                    edges.append(Edge(
                        source_id=sec_node_id,
                        source_type=NodeType.SECTION.value,
                        edge_type=EdgeType.CONTAINS_CLAIM.value,
                        target_id=node_id,
                        target_type=NodeType.CLAIM.value,
                        evidence=ent.get("evidence"),
                    ))

            # Connect main Paper to Entity (Methods, Datasets, Tasks, Metrics) via USES / MENTIONS
            elif node_type_val in {NodeType.METHOD.value, NodeType.DATASET.value, NodeType.TASK.value, NodeType.METRIC.value}:
                # Determine appropriate edge type
                edge_type_val = EdgeType.MENTIONS.value
                if node_type_val == NodeType.METHOD.value:
                    # If mentioned in Title or Abstract, it might be INTRODUCES, else USES_METHOD
                    is_introduced = (
                        ent.get("source_section", "").lower() in {"abstract", "title"} or
                        any(term in ent["name"].lower() for term in (title.lower()).split())
                    )
                    edge_type_val = EdgeType.INTRODUCES.value if is_introduced else EdgeType.USES_METHOD.value
                elif node_type_val == NodeType.DATASET.value:
                    edge_type_val = EdgeType.USES_DATASET.value
                elif node_type_val == NodeType.TASK.value:
                    edge_type_val = EdgeType.SOLVES_TASK.value

                # Create the edge from Paper -> Entity
                if self.validator.validate_edge(NodeType.PAPER.value, edge_type_val, node_type_val):
                    edges.append(Edge(
                        source_id=main_paper_node.node_id,
                        source_type=NodeType.PAPER.value,
                        edge_type=edge_type_val,
                        target_id=node_id,
                        target_type=node_type_val,
                        evidence=ent.get("evidence"),
                        confidence=ent["confidence_parsed"],
                    ))

        # 6. Add Extracted Relations as Edges
        for rel in relations:
            src_name = rel.get("source")
            src_type = rel.get("source_type")
            rel_type = rel.get("relation")
            tgt_name = rel.get("target")
            tgt_type = rel.get("target_type")
            evidence = rel.get("evidence")
            confidence = float(rel.get("confidence") if rel.get("confidence") is not None else 1.0)

            if not src_name or not src_type or not rel_type or not tgt_name or not tgt_type:
                continue

            src_node_id = entity_key_to_id.get((src_type.lower(), src_name.lower()))
            tgt_node_id = entity_key_to_id.get((tgt_type.lower(), tgt_name.lower()))

            # If the entities exist in the graph, we connect them
            if src_node_id and tgt_node_id:
                if self.validator.validate_edge(src_type, rel_type, tgt_type):
                    edges.append(Edge(
                        source_id=src_node_id,
                        source_type=src_type,
                        edge_type=rel_type,
                        target_id=tgt_node_id,
                        target_type=tgt_type,
                        evidence=evidence,
                        confidence=confidence,
                    ))

        # Convert all to dictionary format
        serialized_nodes = [node.to_dict() for node in nodes_map.values()]
        serialized_edges = [edge.to_dict() for edge in edges]

        logger.info(
            "paper_graph_built",
            paper_id=paper_id,
            nodes_count=len(serialized_nodes),
            edges_count=len(serialized_edges),
        )

        return {
            "nodes": serialized_nodes,
            "edges": serialized_edges,
        }

    def _hash_str(self, val: str) -> str:
        """Returns a stable 16-character sha256 hash slice of a string."""
        return hashlib.sha256(val.lower().strip().encode("utf-8")).hexdigest()[:16]

    def _generate_node_id(self, node_type: str, paper_id: str, name: str) -> str:
        """Generates a unique and stable node ID."""
        name_hash = self._hash_str(name)
        return f"{node_type.lower()}_{paper_id}_{name_hash}"
