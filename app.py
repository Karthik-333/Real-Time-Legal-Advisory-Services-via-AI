from flask import Flask, render_template, jsonify, redirect, url_for, request, Blueprint
from flask_login import LoginManager, login_required, current_user
from flask_cors import CORS
import os
import logging
from datetime import datetime
import speech_recognition as sr

from models import db, User
from routes.auth import auth_bp
from routes.chat import chat_bp, init_chat_services
from routes.document import document_bp, init_document_services

from services.llm_service import LLMService
from services.document_service import DocumentService
from services.tts_service import TTSService
from services.precedent_service import PrecedentService
from services.background_processor import BackgroundProcessor
from services.translation_service import TranslationService

from config import Config

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@main_bp.route('/documents')
@login_required
def documents():
    return render_template('documents.html')

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    CORS(app)
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    llm_service = LLMService(app.config['OLLAMA_API_URL'], app.config['OLLAMA_MODEL'])
    document_service = DocumentService(app.config['UPLOAD_FOLDER'], app.config['ALLOWED_EXTENSIONS'])
    tts_service = TTSService('static', app.config['TTS_LANGUAGES'])
    precedent_service = PrecedentService(app.config['PRECEDENTS_FILE'])
    translation_service = TranslationService()
    
    init_chat_services(llm_service, tts_service, precedent_service)
    init_document_services(document_service, llm_service)
    
    background_processor = BackgroundProcessor(app, llm_service)
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(document_bp)
    
    @app.route('/health')
    def health_check():
        services_status = {
            'database': True,
            'ollama': llm_service.is_available(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            db.session.execute('SELECT 1')
        except Exception as e:
            services_status['database'] = False
            logger.error(f"Database health check failed: {e}")
        
        return jsonify(services_status)
    
    @app.route('/static/precedents.json')
    def serve_precedents():
        try:
            import json
            with open(app.config['PRECEDENTS_FILE'], 'r', encoding='utf-8') as f:
                precedents = json.load(f)
            return jsonify(precedents)
        except Exception as e:
            logger.error(f"Error serving precedents: {e}")
            return jsonify([]), 404
    
    @app.route('/translate', methods=['POST'])
    @login_required
    def translate_text():
        try:
            data = request.get_json()
            text = data.get('text', '').strip()
            source_lang = data.get('source_lang', 'english')
            target_lang = data.get('target_lang', 'tamil')

            if not text:
                return jsonify({'error': 'Text is required'}), 400

            translated_text = translation_service.translate_text(text, source_lang, target_lang)
            
            return jsonify({
                'success': True,
                'original_text': text,
                'translated_text': translated_text,
                'source_language': source_lang,
                'target_language': target_lang
            })

        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return jsonify({'error': 'Translation failed'}), 500
    
    @app.route('/tts/generate', methods=['POST'])
    @login_required
    def generate_tts():
        try:
            data = request.get_json()
            text = data.get('text', '').strip()
            language = data.get('ttsLanguage') or data.get('language') or current_user.preferred_language

            if not text:
                return jsonify({'error': 'Text is required'}), 400

            if language != 'english':
                text = translation_service.translate_text(text, 'english', language)

            audio_file = tts_service.generate_speech(text, language)
            if audio_file:
                return jsonify({'success': True, 'audio_file': audio_file})
            else:
                return jsonify({'error': 'Failed to generate audio'}), 500

        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return jsonify({'error': 'TTS generation failed'}), 500
    
    @app.route('/voice-to-text', methods=['POST'])
    @login_required
    def voice_to_text():
        try:
            if 'audio' not in request.files:
                return jsonify({'error': 'No audio file provided'}), 400

            audio_file = request.files['audio']
            recognizer = sr.Recognizer()

            with sr.AudioFile(audio_file) as source:
                audio_data = recognizer.record(source)

            try:
                text = recognizer.recognize_google(audio_data)
                return jsonify({'success': True, 'text': text})
            except sr.UnknownValueError:
                return jsonify({'error': 'Speech not recognized'}), 400
            except sr.RequestError as e:
                return jsonify({'error': f'Speech recognition service error: {e}'}), 500

        except Exception as e:
            logger.error(f"Error processing audio file: {e}")
            return jsonify({'error': 'Failed to process audio file'}), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
    
    with app.app_context():
        db.create_all()
        
        demo_user = User.query.filter_by(username='demo').first()
        if not demo_user:
            demo_user = User(
                username='demo',
                email='demo@example.com',
                preferred_language='english'
            )
            demo_user.set_password('demo123')
            db.session.add(demo_user)
            db.session.commit()
            logger.info("Demo user created: username='demo', password='demo123'")
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    from services.llm_service import LLMService
    llm_service = LLMService(app.config['OLLAMA_API_URL'], app.config['OLLAMA_MODEL'])
    background_processor = BackgroundProcessor(app, llm_service)
    background_processor.start()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    try:
        app.run(host='0.0.0.0', port=port, debug=debug)
    finally:
        background_processor.stop()
