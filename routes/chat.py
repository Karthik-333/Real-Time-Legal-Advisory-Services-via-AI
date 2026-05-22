from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
from models import db, Chat, Message
from services.llm_service import LLMService
from services.tts_service import TTSService
from services.precedent_service import PrecedentService
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

llm_service = None
tts_service = None
precedent_service = None

def init_chat_services(llm, tts, precedent):
    global llm_service, tts_service, precedent_service
    llm_service = llm
    tts_service = tts
    precedent_service = precedent

@chat_bp.route('/send', methods=['POST'])
@login_required
def send_message():
    try:
        logger.info("Chat send endpoint called")
        data = request.get_json()
        logger.info(f"Request data: {data}")
        
        message_content = data.get('message', '').strip()
        chat_id = data.get('chat_id')
        language = data.get('language', current_user.preferred_language)
        enable_precedents = data.get('enable_precedents', False)
        tts_language = data.get('ttsLanguage', 'en')
        document_id = data.get('document_id')
        
        logger.info(f"Parsed data: message='{message_content}', chat_id={chat_id}, enable_precedents={enable_precedents}, document_id={document_id}")
        
        if not message_content:
            logger.warning("Empty message received")
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if chat_id:
            chat = Chat.query.filter_by(id=chat_id, user_id=current_user.id).first()
            if not chat:
                return jsonify({'error': 'Chat not found'}), 404
        else:
            chat = Chat(
                user_id=current_user.id,
                title=message_content[:50] + "..." if len(message_content) > 50 else message_content
            )
            db.session.add(chat)
            db.session.flush()
        
        user_message = Message(
            chat_id=chat.id,
            content=message_content,
            is_user=True,
            language=language
        )
        db.session.add(user_message)
        
        context = ""
        precedent_context = ""
        document_context = ""
        
        if 'this case' in message_content.lower() or 'this document' in message_content.lower() or 'uploaded' in message_content.lower():
            from models import Document
            recent_doc = Document.query.filter_by(user_id=current_user.id)\
                                     .order_by(Document.uploaded_at.desc())\
                                     .first()
            if recent_doc and recent_doc.content_text:
                document_context = f"📄 **Recently Uploaded Document: {recent_doc.original_filename}**\n\n"
                if recent_doc.document_type:
                    document_context += f"**Type:** {recent_doc.document_type}\n"
                if recent_doc.case_number:
                    document_context += f"**Case:** {recent_doc.case_number}\n"
                if recent_doc.court:
                    document_context += f"**Court:** {recent_doc.court}\n"
                document_context += f"\n**Content:**\n{recent_doc.content_text[:2000]}{'...' if len(recent_doc.content_text) > 2000 else ''}\n\n"
        
        if enable_precedents and precedent_service:
            similar_precedents = precedent_service.find_similar_precedents(message_content)
            if similar_precedents:
                precedent_context = "📚 **Legal Precedents Found:**\n\n"
                for i, precedent in enumerate(similar_precedents[:3], 1):
                    precedent_context += f"**{i}. {precedent_service.format_precedent_for_display(precedent)}**\n\n"
        
        context = document_context + precedent_context
        
        db.session.commit()
        
        logger.info(f"Message saved, returning response with chat_id={chat.id}")
        doc_param = f"&document_id={document_id}" if document_id else ""
        return jsonify({
            'success': True,
            'chat_id': chat.id,
            'user_message': user_message.to_dict(),
            'stream_url': f'/chat/stream/{chat.id}?language={language}&tts_language={tts_language}&enable_precedents={str(enable_precedents).lower()}{doc_param}'
        })
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to send message'}), 500

@chat_bp.route('/stream/<int:chat_id>')
@login_required
def stream_response(chat_id):
    try:
        language = request.args.get('language', current_user.preferred_language)
        tts_language = request.args.get('tts_language', 'en')
        enable_precedents = request.args.get('enable_precedents', 'false').lower() == 'true'
        document_id = request.args.get('document_id', type=int)
        
        logger.info(f"Stream request: chat_id={chat_id}, language={language}, tts_language={tts_language}, enable_precedents={enable_precedents}, document_id={document_id}")
        
        from flask import current_app
        app = current_app._get_current_object()
        
        chat = Chat.query.filter_by(id=chat_id, user_id=current_user.id).first()
        if not chat:
            logger.error(f"Chat {chat_id} not found for user {current_user.id}")
            return jsonify({'error': 'Chat not found'}), 404
        
        last_user_message = Message.query.filter_by(
            chat_id=chat_id, is_user=True
        ).order_by(Message.timestamp.desc()).first()
        
        if not last_user_message:
            logger.error(f"No user message found for chat {chat_id}")
            return jsonify({'error': 'No user message found'}), 404
        
        logger.info(f"Processing message: {last_user_message.content[:50]}...")
        
        context = ""
        
        previous_messages = Message.query.filter_by(chat_id=chat_id)\
                                         .order_by(Message.timestamp.desc())\
                                         .limit(11).all()
        previous_messages = list(reversed(previous_messages))[:-1]
        
        if previous_messages:
            context += "**Previous Conversation:**\n"
            for msg in previous_messages[-10:]:
                role = "User" if msg.is_user else "AI"
                content_preview = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                context += f"{role}: {content_preview}\n\n"
            context += "---\n\n"
        
        if document_id:
            from models import Document
            attached_doc = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
            if attached_doc and attached_doc.content_text:
                logger.info(f"Loading attached document: {attached_doc.original_filename}")
                context += f"📄 **Attached Document: {attached_doc.original_filename}**\n\n"
                if attached_doc.document_type:
                    context += f"**Type:** {attached_doc.document_type}\n"
                if attached_doc.case_number:
                    context += f"**Case:** {attached_doc.case_number}\n"
                if attached_doc.court:
                    context += f"**Court:** {attached_doc.court}\n"
                context += f"\n**Document Content:**\n{attached_doc.content_text[:4000]}{'...' if len(attached_doc.content_text) > 4000 else ''}\n\n"
        elif 'this case' in last_user_message.content.lower() or 'this document' in last_user_message.content.lower() or 'uploaded' in last_user_message.content.lower():
            from models import Document
            recent_doc = Document.query.filter_by(user_id=current_user.id)\
                                     .order_by(Document.uploaded_at.desc())\
                                     .first()
            if recent_doc and recent_doc.content_text:
                context += f"📄 **Recently Uploaded Document: {recent_doc.original_filename}**\n\n"
                if recent_doc.document_type:
                    context += f"**Type:** {recent_doc.document_type}\n"
                if recent_doc.case_number:
                    context += f"**Case:** {recent_doc.case_number}\n"
                if recent_doc.court:
                    context += f"**Court:** {recent_doc.court}\n"
                context += f"\n**Document Content:**\n{recent_doc.content_text[:2000]}{'...' if len(recent_doc.content_text) > 2000 else ''}\n\n"
        
        if enable_precedents and precedent_service:
            logger.info("Precedents enabled, searching for similar cases...")
            similar_precedents = precedent_service.find_similar_precedents(last_user_message.content)
            if similar_precedents:
                logger.info(f"Found {len(similar_precedents)} similar precedents")
                context += "📚 **Relevant Legal Precedents (from Indian case law database):**\n\n"
                for i, precedent in enumerate(similar_precedents[:3], 1):
                    formatted_precedent = precedent_service.format_precedent_for_display(precedent)
                    context += f"**{i}. {formatted_precedent}**\n\n"
                context += "Please refer to these precedents when answering the user's question.\n\n"
            else:
                logger.info("No similar precedents found")
        
        if context:
            context += "**User's Question:** " + last_user_message.content + "\n\n"
        
        def generate():
            ai_message_dict = None
            
            response_lang = 'english'
            if tts_language.lower() in ['hi', 'hindi']:
                response_lang = 'hindi'
            elif tts_language.lower() in ['ta', 'tamil']:
                response_lang = 'tamil'
            
            try:
                ai_response = ""
                logger.info(f"Starting AI response generation in {response_lang}")
                
                if llm_service and llm_service.is_available():
                    logger.info("LLM service is available, generating response...")
                    
                    for chunk in llm_service.generate_response(
                        last_user_message.content, 
                        context=context, 
                        language=response_lang
                    ):
                        ai_response += chunk
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                    
                    logger.info(f"AI response in {response_lang}, length: {len(ai_response)}")
                else:
                    error_msg = "AI service is currently unavailable. Please ensure Ollama is running with the Gemma3:1b model."
                    logger.warning("LLM service not available")
                    ai_response = error_msg
                    yield f"data: {json.dumps({'type': 'token', 'content': error_msg})}\n\n"
                
                with app.app_context():
                    ai_message = Message(
                        chat_id=chat_id,
                        content=ai_response,
                        is_user=False,
                        language=language
                    )
                    db.session.add(ai_message)
                    db.session.commit()
                    
                    ai_message_dict = ai_message.to_dict()
                
                yield f"data: {json.dumps({'type': 'complete', 'message': ai_message_dict})}\n\n"
                
                with app.app_context():
                    if tts_service and ai_response.strip():
                        tts_lang_map = {
                            'en': 'english',
                            'ta': 'tamil', 
                            'hi': 'hindi'
                        }
                        tts_lang = tts_lang_map.get(tts_language, 'english')
                        logger.info(f"Generating TTS: tts_language={tts_language}, mapped_lang={tts_lang}")
                        audio_file = tts_service.generate_speech(ai_response, tts_lang)
                        if audio_file:
                            msg = Message.query.get(ai_message_dict['id'])
                            if msg:
                                msg.audio_file = audio_file
                                db.session.commit()
                            logger.info(f"TTS audio generated: {audio_file}")
                
            except Exception as e:
                logger.error(f"Error in stream generation: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error in stream response: {e}")
        return jsonify({'error': 'Failed to generate response'}), 500

@chat_bp.route('/history')
@login_required
def get_chat_history():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        chats = Chat.query.filter_by(user_id=current_user.id)\
                          .order_by(Chat.updated_at.desc())\
                          .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'chats': [chat.to_dict() for chat in chats.items],
            'total': chats.total,
            'pages': chats.pages,
            'current_page': page
        })
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        return jsonify({'error': 'Failed to get chat history'}), 500

@chat_bp.route('/<int:chat_id>/messages')
@login_required
def get_chat_messages(chat_id):
    try:
        chat = Chat.query.filter_by(id=chat_id, user_id=current_user.id).first()
        if not chat:
            return jsonify({'error': 'Chat not found'}), 404
        
        messages = Message.query.filter_by(chat_id=chat_id)\
                                .order_by(Message.timestamp.asc())\
                                .all()
        
        return jsonify({
            'chat': chat.to_dict(),
            'messages': [message.to_dict() for message in messages]
        })
        
    except Exception as e:
        logger.error(f"Error getting chat messages: {e}")
        return jsonify({'error': 'Failed to get messages'}), 500

@chat_bp.route('/<int:chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    try:
        chat = Chat.query.filter_by(id=chat_id, user_id=current_user.id).first()
        if not chat:
            return jsonify({'error': 'Chat not found'}), 404
        
        if tts_service:
            for message in chat.messages:
                if message.audio_file:
                    tts_service.delete_audio_file(message.audio_file)
        
        db.session.delete(chat)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting chat: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete chat'}), 500

@chat_bp.route('/precedents/search', methods=['POST'])
@login_required
def search_precedents():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        legal_area = data.get('legal_area')
        limit = data.get('limit', 5)
        
        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400
        
        if not precedent_service:
            return jsonify({'error': 'Precedent service unavailable'}), 503
        
        precedents = precedent_service.find_similar_precedents(query, legal_area, limit)
        
        return jsonify({
            'precedents': precedents,
            'count': len(precedents)
        })
        
    except Exception as e:
        logger.error(f"Error searching precedents: {e}")
        return jsonify({'error': 'Failed to search precedents'}), 500
