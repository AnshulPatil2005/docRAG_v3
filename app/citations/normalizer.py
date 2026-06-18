"""
Citation Normalizer Module

Normalizes citation metadata and handles deduplication.
"""

import structlog
from typing import List, Dict, Any, Optional

logger = structlog.get_logger()

class CitationNormalizer:
    """
    Normalizes and deduplicates citations.
    """

    def normalize_list(self, references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize a list of references and merge duplicates.
        Merging is based on DOI or arXiv ID.
        """
        normalized_refs = []
        seen_doi = {}      # doi -> index in normalized_refs
        seen_arxiv = {}    # arxiv_id -> index in normalized_refs

        for ref in references:
            normalized_ref = self.normalize_single(ref)

            doi = normalized_ref.get("doi")
            arxiv_id = normalized_ref.get("arxiv_id")

            existing_idx = None
            if doi and doi in seen_doi:
                existing_idx = seen_doi[doi]
            elif arxiv_id and arxiv_id in seen_arxiv:
                existing_idx = seen_arxiv[arxiv_id]

            if existing_idx is not None:
                # Merge logic
                self._merge_references(normalized_refs[existing_idx], normalized_ref)
            else:
                current_idx = len(normalized_refs)
                normalized_refs.append(normalized_ref)
                if doi:
                    seen_doi[doi] = current_idx
                if arxiv_id:
                    seen_arxiv[arxiv_id] = current_idx

        return normalized_refs

    def normalize_single(self, ref: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single reference's metadata."""
        normalized = {
            "title": self._clean_string(ref.get("title")),
            "authors": [self._clean_string(a) for a in ref.get("authors", []) if a],
            "year": ref.get("year"),
            "doi": self._clean_identifier(ref.get("doi")),
            "arxiv_id": self._clean_identifier(ref.get("arxiv_id")),
            "ref_id": ref.get("ref_id"),
            "raw": ref.get("raw")
        }
        return normalized

    def _clean_string(self, s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        # Remove extra whitespace and common artifacts
        s = s.strip(" \t\n\r,;:")
        import re
        s = re.sub(r"\s+", " ", s)
        return s

    def _clean_identifier(self, ident: Optional[str]) -> Optional[str]:
        if not ident:
            return None
        return ident.strip().lower()

    def _merge_references(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge source into target in-place."""
        # Keep the most complete information
        if not target.get("title") and source.get("title"):
            target["title"] = source["title"]

        if not target.get("authors") and source.get("authors"):
            target["authors"] = source["authors"]

        if not target.get("year") and source.get("year"):
            target["year"] = source["year"]

        if not target.get("doi") and source.get("doi"):
            target["doi"] = source["doi"]

        if not target.get("arxiv_id") and source.get("arxiv_id"):
            target["arxiv_id"] = source["arxiv_id"]

        # We might want to keep track of all ref_ids associated with this merged entity
        if "ref_ids" not in target:
            target["ref_ids"] = [target.get("ref_id")] if target.get("ref_id") else []

        source_ref_id = source.get("ref_id")
        if source_ref_id and source_ref_id not in target["ref_ids"]:
            target["ref_ids"].append(source_ref_id)
