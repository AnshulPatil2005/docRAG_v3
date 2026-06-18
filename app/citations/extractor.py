"""
Citation Extractor Module

Extracts bibliography items and in-text citations from research papers.
"""

import re
import structlog
from typing import List, Dict, Optional, Any

logger = structlog.get_logger()

class CitationExtractor:
    """
    Extracts citations and references from paper text using regex.
    """

    # Patterns for identifying the reference section
    REF_SECTION_PATTERNS = [
        r"(?:^|\n)(References?|Bibliography|WORKS CITED)\s*(?:\n|:)",
    ]

    # Patterns for bibliography items
    # Typically: [1] Author, Title, Year.
    # Or: Author (Year). Title.
    BIB_ITEM_PATTERNS = [
        r"(?:^|\n)\[(\d+)\]\s+(.*?)(?=\n\[\d+\]|\n\n|$)",  # [1] Style
        r"(?:^|\n)(\d+)\.\s+(.*?)(?=\n\d+\.|\n\n|$)",      # 1. Style
    ]

    # Patterns for in-text mentions
    # [1], [1, 2], [1-3]
    # (Author, 2020)
    MENTION_PATTERNS = [
        r"\[(\d+(?:,\s*\d+|-\d+)*)\]",
        r"\(([^)]*?\d{4}[^)]*?)\)",
    ]

    def __init__(self):
        self.ref_section_regex = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.REF_SECTION_PATTERNS]

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract bibliography and mentions from full text.
        """
        ref_section = self._find_reference_section(text)
        if not ref_section:
            logger.warning("reference_section_not_found")
            return {"references": [], "mentions": []}

        references = self._parse_bibliography(ref_section)
        mentions = self._find_mentions(text, references)

        return {
            "references": references,
            "mentions": mentions
        }

    def _find_reference_section(self, text: str) -> Optional[str]:
        """Find the start of the reference section and return everything after it."""
        for pattern in self.ref_section_regex:
            match = pattern.search(text)
            if match:
                return text[match.end():].strip()
        return None

    def _parse_bibliography(self, ref_text: str) -> List[Dict[str, Any]]:
        """Parse the bibliography section into individual references."""
        references = []

        # Try to find numbered items first
        found_numbered = False
        for pattern in self.BIB_ITEM_PATTERNS:
            regex = re.compile(pattern, re.DOTALL)
            matches = list(regex.finditer(ref_text))
            if matches:
                found_numbered = True
                for match in matches:
                    ref_id = match.group(1)
                    content = match.group(2).strip()
                    ref_data = self._parse_reference_content(content)
                    ref_data["ref_id"] = ref_id
                    references.append(ref_data)
                break

        # If no numbered items, split by double newline as a fallback
        if not found_numbered:
            blocks = re.split(r"\n\s*\n", ref_text)
            for i, block in enumerate(blocks):
                content = block.strip()
                if len(content) > 10:
                    ref_data = self._parse_reference_content(content)
                    ref_data["ref_id"] = str(i + 1)
                    references.append(ref_data)

        return references

    def _parse_reference_content(self, content: str) -> Dict[str, Any]:
        """Extract metadata from a single reference string."""
        ref = {
            "title": None,
            "authors": [],
            "year": None,
            "doi": None,
            "arxiv_id": None,
            "raw": content
        }

        # Normalize whitespace
        content = re.sub(r"\s+", " ", content)

        # DOI
        doi_match = re.search(r"doi:\s*([\d.]+/[\w./-]+)", content, re.IGNORECASE)
        if not doi_match:
             doi_match = re.search(r"https?://(?:dx\.)?doi\.org/([\d.]+/[\w./-]+)", content)
        if doi_match:
            ref["doi"] = doi_match.group(1).strip()

        # arXiv
        arxiv_match = re.search(r"arxiv:\s*(\d+\.\d+)", content, re.IGNORECASE)
        if not arxiv_match:
            arxiv_match = re.search(r"abs/(\d+\.\d+)", content)
        if arxiv_match:
            ref["arxiv_id"] = arxiv_match.group(1).strip()

        # Year
        year_match = re.search(r"\b(19|20)\d{2}\b", content)
        if year_match:
            ref["year"] = int(year_match.group(0))

        # Title and Authors - complex with regex, but let's do a best effort
        # Heuristic: Title is often in quotes or follows authors and a year
        title_match = re.search(r'["\u201c](.*?)["\u201d]', content)
        if title_match:
            ref["title"] = title_match.group(1).strip()

        # Simple split for authors (everything before the first year or title)
        parts = []
        if ref["year"]:
            parts = content.split(str(ref["year"]), 1)
        elif ref["title"]:
            parts = content.split(ref["title"], 1)

        if parts:
            authors_part = parts[0].strip(" ,.")
            # Remove leading numbers/brackets if any
            authors_part = re.sub(r"^\[\d+\]\s*", "", authors_part)
            authors_part = re.sub(r"^\d+\.\s*", "", authors_part)

            # Split by common separators
            author_list = re.split(r",\s*|\s+and\s+", authors_part)
            ref["authors"] = [a.strip() for a in author_list if a.strip() and len(a.strip()) > 1]

        # If title still None, try another heuristic: after authors
        if not ref["title"] and parts and len(parts) > 1:
            title_part = parts[1].strip(" ,.")
            # Take first sentence or first 100 chars
            title_match = re.search(r"^(.*?)\.", title_part)
            if title_match:
                ref["title"] = title_match.group(1).strip()
            else:
                ref["title"] = title_part[:100].strip()

        # Final fallback for title
        if not ref["title"]:
            ref["title"] = content[:100].strip()

        return ref

    def _find_mentions(self, text: str, references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find where references are mentioned in the text."""
        mentions = []

        # Create a mapping of ref_id to reference for quick lookup
        ref_map = {ref["ref_id"]: ref for ref in references if ref.get("ref_id")}

        for pattern in self.MENTION_PATTERNS:
            regex = re.compile(pattern)
            for match in regex.finditer(text):
                mention_text = match.group(0)
                content = match.group(1)

                # Handle [1, 2, 3] or [1-3]
                ids = []
                if "-" in content and re.match(r"^\d+-\d+$", content):
                    start, end = map(int, content.split("-"))
                    ids = [str(i) for i in range(start, end + 1)]
                else:
                    ids = [i.strip() for i in re.split(r",\s*", content)]

                # Context (surrounding text)
                start, end = match.span()
                context_start = max(0, start - 100)
                context_end = min(len(text), end + 100)
                context = text[context_start:context_end].strip()

                for ref_id in ids:
                    if ref_id in ref_map:
                        mentions.append({
                            "ref_id": ref_id,
                            "mention_text": mention_text,
                            "context": context,
                            "start_offset": start,
                            "end_offset": end
                        })

        return mentions
