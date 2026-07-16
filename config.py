import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///legal_ai.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
    
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    OLLAMA_API_URL = 'http://localhost:11434'
    OLLAMA_MODEL = 'llama3.2:latest'
    
    TTS_LANGUAGES = {
        'english': 'en',
        'tamil': 'ta', 
        'hindi': 'hi'
    }
    
    PRECEDENTS_FILE = 'data/precedents.json'
