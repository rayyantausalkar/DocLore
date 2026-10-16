from typing import Optional
from doclore_api.diagnostics.models import Citation
from doclore_api.retrieval.models import Evidence


class CitationValidator:
    """Validates and constructs verified citations strictly grounded in retrieved evidence."""

    @staticmethod
    def validate_and_build_citations(
        retrieved_evidence: list[Evidence],
        max_citations: int = 5,
    ) -> list[Citation]:
        """Converts retrieved evidence into verified citations preserving exact provenance."""
        citations: list[Citation] = []
        seen_chunks: set[str] = set()

        for ev in retrieved_evidence:
            if ev.chunk_id in seen_chunks:
                continue
            seen_chunks.add(ev.chunk_id)

            prov = ev.provenance
            # Truncate snippet to 350 chars if too long
            snippet = ev.text.strip()
            if len(snippet) > 400:
                snippet = snippet[:397] + "..."

            citations.append(
                Citation(
                    source_id=prov.source_id,
                    document_id=prov.document_id,
                    chunk_id=ev.chunk_id,
                    source_type=prov.source_type,
                    canonical_path=prov.canonical_path,
                    start_line=prov.start_line,
                    end_line=prov.end_line,
                    section_path=prov.section_path,
                    snippet=snippet,
                    relevance_note=f"Matched via {ev.match_type} search (RRF score: {ev.rrf_score:.4f})",
                )
            )

            if len(citations) >= max_citations:
                break

        return citations
