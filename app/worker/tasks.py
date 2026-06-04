from app.worker.celery_app import celery_app
from celery.utils.log import get_task_logger
import time
import os
from app.services.ocr import extract_text_from_pdf
from app.services.text_processing import chunk_text
from app.services.embeddings import generate_embeddings
from app.services.vector_store import upsert_vectors
from app.core.config import settings

logger = get_task_logger(__name__)

@celery_app.task(bind=True, name="app.worker.tasks.process_pdf_task", max_retries=3)
def process_pdf_task(self, doc_id: str, file_path: str):
    try:
        logger.info(f"Starting processing for doc_id: {doc_id}")
        self.update_state(state='PROCESSING', meta={'step': 'OCR', 'doc_id': doc_id})
        
        # 1. OCR
        logger.info("Step 1: OCR Extraction")
        pages_text = extract_text_from_pdf(file_path) # Returns list of (page_num, text)
        
        if not pages_text:
            logger.warning("No text extracted from PDF.")
            return {"status": "failed", "reason": "No text extracted"}

        self.update_state(state='PROCESSING', meta={'step': 'CHUNKING', 'doc_id': doc_id})

        # 2. Chunking
        logger.info("Step 2: Chunking")
        chunks = chunk_text(pages_text, doc_id)
        
        self.update_state(state='PROCESSING', meta={'step': 'EMBEDDING', 'doc_id': doc_id})
        
        # 3. Embeddings
        logger.info("Step 3: Generating Embeddings")
        embeddings_data = generate_embeddings(chunks) # Returns list of (vector, payload)
        
        self.update_state(state='PROCESSING', meta={'step': 'UPSERTING', 'doc_id': doc_id})
        
        # 4. Upsert to Qdrant
        logger.info("Step 4: Upserting to Qdrant")
        upsert_vectors(settings.QDRANT_COLLECTION_NAME, embeddings_data)
        
        logger.info(f"Processing complete for doc_id: {doc_id}")
        return {"status": "completed", "doc_id": doc_id, "chunks_count": len(chunks)}
        
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        # self.retry(exc=e, countdown=2 ** self.request.retries)
        raise e
