import threading
import time
import logging
from models import db, Document
from flask import current_app

logger = logging.getLogger(__name__)

class BackgroundProcessor:
    def __init__(self, app, llm_service):
        self.app = app
        self.llm_service = llm_service
        self.running = False
        self.thread = None
        
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._process_loop, daemon=True)
            self.thread.start()
            logger.info("Background processor started")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Background processor stopped")
    
    def _process_loop(self):
        while self.running:
            try:
                with self.app.app_context():
                    self._process_pending_documents()
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error in background processor: {e}")
                time.sleep(30)
    
    def _process_pending_documents(self):
        try:
            pending_docs = Document.query.filter_by(processed=False).limit(5).all()
            
            for doc in pending_docs:
                if not self.running:
                    break
                    
                try:
                    self._process_document(doc)
                except Exception as e:
                    logger.error(f"Error processing document {doc.id}: {e}")
                    doc.processed = True
                    db.session.commit()
        
        except Exception as e:
            logger.error(f"Error querying pending documents: {e}")
    
    def _process_document(self, doc):
        if not doc.content_text:
            doc.processed = True
            db.session.commit()
            return
        
        logger.info(f"Processing document {doc.id}: {doc.original_filename}")
        
        try:
            if not doc.summary and len(doc.content_text.strip()) > 50:
                if self.llm_service and self.llm_service.is_available():
                    summary = self.llm_service.generate_summary(doc.content_text, "legal document")
                    if summary and not summary.startswith("Error"):
                        doc.summary = summary
                else:
                    doc.summary = "AI service unavailable - summary will be generated when service is restored"
            
            if not doc.document_type:
                if self.llm_service and self.llm_service.is_available():
                    analysis = self.llm_service.analyze_document_type(doc.content_text)
                    if analysis and not analysis.get('error'):
                        doc.document_type = analysis.get('document_type', 'legal document')
                        doc.jurisdiction = analysis.get('jurisdiction')
                        doc.case_number = analysis.get('case_number')
                        doc.court = analysis.get('court')
                else:
                    doc.document_type = 'legal document'
            
            doc.processed = True
            db.session.commit()
            logger.info(f"Successfully processed document {doc.id}")
            
        except Exception as e:
            logger.error(f"Failed to process document {doc.id}: {e}")
            doc.processed = True
            if not doc.summary:
                doc.summary = "Processing failed - please reprocess document"
            if not doc.document_type:
                doc.document_type = "unknown"
            db.session.commit()
