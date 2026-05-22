from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Document
from services.document_service import DocumentService
from services.llm_service import LLMService
import os
import logging

logger = logging.getLogger(__name__)

document_bp = Blueprint('document', __name__, url_prefix='/document')

document_service = None
llm_service = None

def init_document_services(doc_service, llm):
    global document_service, llm_service
    document_service = doc_service
    llm_service = llm

@document_bp.route('/upload', methods=['POST'])
@login_required
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not document_service.allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        file_info = document_service.get_file_info(file)
        
        if file_info['size'] > current_app.config['MAX_CONTENT_LENGTH']:
            return jsonify({'error': 'File too large'}), 400
        
        filename, file_path = document_service.save_file(file, current_user.id)
        if not filename:
            return jsonify({'error': 'Failed to save file'}), 500
        
        document = Document(
            user_id=current_user.id,
            filename=filename,
            original_filename=file.filename,
            file_path=file_path,
            file_type=file_info['type'],
            file_size=file_info['size'],
            processed=False
        )
        
        db.session.add(document)
        db.session.commit()
        
        validation = {'is_valid': True, 'issues': [], 'confidence': 'high'}
        try:
            content_text = document_service.extract_text(file_path, file_info['type'])
            
            document = db.session.get(Document, document.id)
            document.content_text = content_text
            
            validation = document_service.validate_legal_document(content_text)
            
            if llm_service and llm_service.is_available() and content_text.strip():
                content_length = len(content_text)
                
                if content_length < 5000:
                    try:
                        summary = llm_service.generate_summary(content_text, "legal document")
                        if summary and not summary.startswith("Error") and not summary.startswith("Summary generation timed out"):
                            document.summary = summary
                        
                        analysis = llm_service.analyze_document_type(content_text)
                        if analysis and not analysis.get('error'):
                            document.document_type = analysis.get('document_type')
                            document.jurisdiction = analysis.get('jurisdiction')
                            document.case_number = analysis.get('case_number')
                            document.court = analysis.get('court')
                        
                        document.processed = True
                    except Exception as llm_error:
                        logger.warning(f"Immediate LLM processing failed, will process in background: {llm_error}")
                        document.summary = "Processing in background..."
                        document.processed = False
                else:
                    document.summary = "Processing in background..."
                    document.processed = False
            else:
                document.summary = "AI service unavailable - summary pending"
                document.processed = False
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error processing document content: {e}")
            document = db.session.get(Document, document.id)
            document.processed = False
            document.summary = "Processing failed - please try reprocessing"
            db.session.commit()
            validation = {'is_valid': False, 'issues': ['Error processing document'], 'confidence': 'low'}
        
        return jsonify({
            'success': True,
            'document': document.to_dict(),
            'validation': validation,
            'content_preview': content_text[:500] + "..." if len(content_text) > 500 else content_text,
            'auto_summary': document.summary if document.processed and document.summary else None
        })
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to upload document'}), 500

@document_bp.route('/list')
@login_required
def list_documents():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        documents = Document.query.filter_by(user_id=current_user.id)\
                                  .order_by(Document.uploaded_at.desc())\
                                  .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'documents': [doc.to_dict() for doc in documents.items],
            'total': documents.total,
            'pages': documents.pages,
            'current_page': page
        })
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return jsonify({'error': 'Failed to list documents'}), 500

@document_bp.route('/<int:doc_id>')
@login_required
def get_document(doc_id):
    try:
        document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        return jsonify({
            'document': document.to_dict(),
            'content': document.content_text
        })
        
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        return jsonify({'error': 'Failed to get document'}), 500

@document_bp.route('/<int:doc_id>/query', methods=['POST'])
@login_required
def query_document(doc_id):
    try:
        document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        data = request.get_json()
        query = data.get('query', '').strip()
        language = data.get('language', current_user.preferred_language)
        
        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400
        
        if not document.content_text:
            return jsonify({'error': 'Document content not available'}), 400
        
        if not llm_service or not llm_service.is_available():
            return jsonify({'error': 'AI service unavailable'}), 503
        
        context = f"📄 **Document Analysis: {document.original_filename}**\n\n"
        if document.document_type:
            context += f"**Document Type:** {document.document_type}\n"
        if document.jurisdiction:
            context += f"**Jurisdiction:** {document.jurisdiction}\n"
        if document.court:
            context += f"**Court:** {document.court}\n"
        if document.case_number:
            context += f"**Case Number:** {document.case_number}\n"
        
        context += f"\n**Document Content:**\n{document.content_text[:3000]}{'...' if len(document.content_text) > 3000 else ''}\n\n"
        context += f"**Question about this document:** {query}"
        
        def generate():
            try:
                response = ""
                for chunk in llm_service.generate_response(
                    query,
                    context=context,
                    language=language
                ):
                    response += chunk
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                
                yield f"data: {json.dumps({'type': 'complete', 'response': response})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in document query generation: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        from flask import Response
        import json
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error querying document: {e}")
        return jsonify({'error': 'Failed to query document'}), 500

@document_bp.route('/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    try:
        document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        if document_service and os.path.exists(document.file_path):
            document_service.delete_file(document.file_path)
        
        db.session.delete(document)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete document'}), 500

@document_bp.route('/<int:doc_id>/reprocess', methods=['POST'])
@login_required
def reprocess_document(doc_id):
    try:
        document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        if not os.path.exists(document.file_path):
            return jsonify({'error': 'Document file not found'}), 404
        
        content_text = document_service.extract_text(document.file_path, document.file_type)
        document.content_text = content_text
        
        if llm_service and llm_service.is_available() and content_text.strip():
            summary = llm_service.generate_summary(content_text, "legal document")
            document.summary = summary
            
            analysis = llm_service.analyze_document_type(content_text)
            if analysis and not analysis.get('error'):
                document.document_type = analysis.get('document_type')
                document.jurisdiction = analysis.get('jurisdiction')
                document.case_number = analysis.get('case_number')
                document.court = analysis.get('court')
        
        document.processed = True
        db.session.commit()
        
        return jsonify({
            'success': True,
            'document': document.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error reprocessing document: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to reprocess document'}), 500

@document_bp.route('/status/<int:doc_id>')
@login_required
def document_status(doc_id):
    try:
        document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first()
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        return jsonify({'processed': bool(document.processed)})
    except Exception as e:
        logger.error(f"Error checking document status: {e}")
        return jsonify({'error': 'Failed to get document status'}), 500
