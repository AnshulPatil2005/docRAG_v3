"""
Citation Extractor Module (Phase 4)

Extracts raw reference strings and in-text citation mentions from paper text.
Uses regex patterns to identify bibliography entries.
"""

import re
from typing import Dict, List
import structlog

logger = structlog.get_logger()


class CitationExtractor:
    """
    Extract raw citations from research paper text.

    Identifies two types of citations:
    1. Reference entries in the bibliography section
    2. In-text citation mentions (e.g. "[1]", "(Smith et al., 2020)")
    """

    # Patterns for reference section markers
    REFERENCE_SECTION_PATTERNS = [
        r"\breferences?\b",
        r"\bbibliography\b",
    ]

    # Patterns for individual reference entries (numbered or unnumbered)
    REFERENCE_ENTRY_PATTERNS = [
        # Numbered: [1] Author et al. (Year). Title...
        r"^\s*\[(\d+)\]\s+.+",
        # Unnumbered starting with author surname + year
        r"^\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*[,.(]\s*(?:19|20)\d{2}\b.+",
        # DOI-based
        r"^\s*.*?(?:doi|DOI)[\s:]*10\.\d{4,}/\S+",
        # arXiv-based
        r"^\s*.*?arXiv[\s:]*\d{4}\.\d{4,5}",
    ]

    # In-text citation patterns
    IN_TEXT_PATTERNS = [
        # Numeric: [1], [1,2], [1-3]
        r"\[(\d+(?:\s*[,;]\s*\d+)*(?:\s*[-]\s*\d+)?)\]",
        # Author-year: (Smith et al., 2020)
        r"\((?:[A-Z][a-z]+(?:\s+(?:et\s+al\.?|[A-Z][a-z]+))*,\s*)*(?:19|20)\d{2}\)",
        # Author-only: Smith et al. (2020)
        r"[A-Z][a-z]+(?:\s+(?:et\s+al\.?))?\s*\((?:19|20)\d{2}\)",
    ]

    def extract(self, text: str) -> Dict[str, List]:
        """
        Extract citations from full paper text.

        Args:
            text: Full text of the paper (all pages concatenated)

        Returns:
            Dict with keys:
            - "references": List of raw reference strings found in bibliography
            - "mentions": List of in-text citation strings with positions
        """
        if not text:
            return {"references": [], "mentions": []}

        references = self._extract_references(text)
        mentions = self._extract_mentions(text)

        logger.info(
            "citations_extracted",
            references=len(references),
            mentions=len(mentions),
        )

        return {"references": references, "mentions": mentions}

    def _extract_references(self, text: str) -> List[Dict]:
        """
        Extract individual reference entries from the bibliography section.
        Returns list of dicts with 'raw_text' and 'ref_index' if numbered.
        """
        lines = text.split("\n")
        references = []
        in_ref_section = False
        ref_entry_pattern = re.compile(
            "|".join(f"({p})" for p in self.REFERENCE_ENTRY_PATTERNS),
            re.MULTILINE,
        )

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect reference section start
            if not in_ref_section:
                if any(
                    re.search(p, stripped, re.IGNORECASE)
                    for p in self.REFERENCE_SECTION_PATTERNS
                ) and len(stripped) < 30:
                    in_ref_section = True
                continue

            # Skip empty lines and section-like headings after ref section
            if not stripped:
                continue
            if any(
                re.search(rf"^{p}$", stripped, re.IGNORECASE)
                for p in self.REFERENCE_SECTION_PATTERNS
            ):
                continue

            # Check if this line looks like a reference entry
            if ref_entry_pattern.match(stripped):
                ref_entry = {"raw_text": stripped, "line_number": i}

                # Try to extract reference index from numbered refs [1], [2], etc.
                idx_match = re.match(r"^\s*\[(\d+)\]", stripped)
                if idx_match:
                    ref_entry["ref_index"] = int(idx_match.group(1))
                    ref_entry["ref_id"] = f"ref_{idx_match.group(1)}"

                # Extract DOI if present
                doi_match = re.search(
                    r"(?:doi|DOI)[\s:]*10\.(\d{4,})/(\S+)", stripped, re.IGNORECASE
                )
                if doi_match:
                    ref_entry["doi"] = f"10.{doi_match.group(1)}/{doi_match.group(2)}"

                # Extract arXiv ID if present
                arxiv_match = re.search(
                    r"arXiv[\s.:]*(\d{4}\.\d{4,5})", stripped, re.IGNORECASE
                )
                if arxiv_match:
                    ref_entry["arxiv_id"] = arxiv_match.group(1)

                # Extract year
                year_match = re.search(r"\b(19|20)\d{2}\b", stripped)
                if year_match:
                    ref_entry["year"] = int(year_match.group(0))

                # Try to extract title (text between quotes or after year+period)
                title = self._extract_title_from_ref(stripped)
                if title:
                    ref_entry["title"] = title

                # Try to extract authors
                authors = self._extract_authors_from_ref(stripped)
                if authors:
                    ref_entry["authors"] = authors

                references.append(ref_entry)

        return references

    def _extract_mentions(self, text: str) -> List[Dict]:
        """Extract in-text citation mentions with their positions."""
        mentions = []

        for pattern in self.IN_TEXT_PATTERNS:
            for match in re.finditer(pattern, text):
                mentions.append({
                    "text": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                })

        # Sort by position and deduplicate overlapping mentions
        mentions.sort(key=lambda m: m["start"])
        deduped = []
        for m in mentions:
            if not deduped or m["start"] >= deduped[-1]["end"]:
                deduped.append(m)

        return deduped

    def _extract_title_from_ref(self, raw: str) -> str:
        """Try to extract a paper title from a raw reference string."""
        # Try quoted title first
        title_match = re.search(r'"([^"]+)"', raw)
        if title_match:
            return title_match.group(1).strip()

        title_match = re.search(r"'([^']+)'", raw)
        if title_match:
            return title_match.group(1).strip()

        # Fallback: text after year + period/comma
        year_match = re.search(r"(?:19|20)\d{2}[.,)\]]\s*(.+?)(?:\.\s|$)", raw)
        if year_match:
            title = year_match.group(1).strip()
            # Remove common trailing patterns
            title = re.sub(r"\s*(?:doi|arXiv|available|retrieved|http).*$", "", title, flags=re.IGNORECASE)
            if 5 < len(title) < 300:
                return title

        return ""

    def _extract_authors_from_ref(self, raw: str) -> List[str]:
        """Try to extract author names from a raw reference string."""
        authors = []

        # Simple heuristic: text before the year
        year_match = re.search(r"(?:19|20)\d{2}", raw)
        if year_match:
            before_year = raw[:year_match.start()]
            # Split by common separators
            parts = re.split(r"\s*[,;]\s*", before_year)
            for part in parts:
                part = part.strip()
                # Remove reference index [1]
                part = re.sub(r"^\[\d+\]\s*", "", part)
                # Remove common suffixes
                part = re.sub(r"\s*(?:and|&)\s*$", "", part)
                if part and 2 < len(part) < 80 and not re.match(r"^\d+$", part):
                    authors.append(part)

        return authors