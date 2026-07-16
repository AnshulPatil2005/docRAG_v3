from app.worker.celery_app import celery_app
from celery.utils.log import get_task_logger
import os

from app.core.config import settings
from app.storage.neo4j_client import Neo4jClient
from app.pipeline.paper_ingestion_pipeline import PaperIngestionPipeline

logger = get_task_logger(__name__)


def _create_neo4j_client() -> "Neo4jClient | None":
    """
    Attempt to connect to Neo4j.  Returns None on failure so that
    the pipeline can still run the vector-RAG path without the graph.
    """
    try:
        client = Neo4jClient(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
            database=settings.NEO4J_DATABASE,
        )
        client.connect()
        client.init_schema()
        logger.info("Neo4j connected and schema initialized")
        return client
    except Exception as exc:
        logger.warning(
            "Neo4j not available -- graph pipeline will be skipped: %s", exc
        )
        return None


@celery_app.task(bind=True, name="app.worker.tasks.process_pdf_task", max_retries=3)
def process_pdf_task(self, doc_id: str, file_path: str):
    """
    Process an uploaded PDF through the full ingestion pipeline.

    Pipeline:  PDF -> OCR -> Parse -> Citations -> Entities -> Relations
               -> Graph Build -> Neo4j -> Chunk -> Embed -> Qdrant

    If Neo4j is unreachable the graph steps are gracefully skipped and
    the vector-RAG path still completes.
    """
    try:
        logger.info("Starting processing for doc_id: %s", doc_id)
        self.update_state(state="PROCESSING", meta={"step": "INITIALIZING", "doc_id": doc_id})

        # --- Neo4j connection (optional) ---
        neo4j_client = _create_neo4j_client()

        try:
            pipeline = PaperIngestionPipeline(neo4j_client=neo4j_client)
            result = pipeline.process(paper_id=doc_id, file_path=file_path)
        finally:
            # Always clean up the Neo4j connection
            if neo4j_client is not None:
                try:
                    neo4j_client.close()
                except Exception:
                    pass

        # --- Build return value ---
        if result.status == "FAILED":
            return {
                "status": "failed",
                "doc_id": doc_id,
                "steps": [
                    {"step": s.step_name, "status": s.status.value, "error": s.error}
                    for s in result.steps
                ],
            }

        return {
            "status": "completed" if result.status == "COMPLETED" else "partial",
            "doc_id": doc_id,
            "chunks_count": result.vector_count,
            "citations_count": result.citation_count,
            "entities_count": result.entity_count,
            "relations_count": result.relation_count,
            "graph_nodes_count": result.graph_nodes_count,
            "graph_edges_count": result.graph_edges_count,
            "pipeline_steps": [
                {
                    "step": s.step_name,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                }
                for s in result.steps
            ],
        }

    except Exception as e:
        logger.error("Error processing PDF: %s", e)
        raise e