import os
import uuid
import logging
from gtts import gTTS
from io import BytesIO
import tempfile

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, static_folder: str, languages: dict):
        self.static_folder = static_folder
        self.languages = languages
        self.audio_folder = os.path.join(static_folder, 'audio')
        os.makedirs(self.audio_folder, exist_ok=True)
    
    def generate_speech(self, text: str, language: str = 'english') -> str:
        try:
            lang_code = self.languages.get(language, 'en')
            
            clean_text = self.clean_text_for_tts(text)
            
            if not clean_text.strip():
                raise ValueError("No valid text to convert to speech")
            
            audio_filename = f"tts_{uuid.uuid4().hex}.mp3"
            audio_path = os.path.join(self.audio_folder, audio_filename)
            
            logger.info(f"Generating TTS: language={language}, lang_code={lang_code}, text_length={len(clean_text)}")
            
            if lang_code != 'en':
                try:
                    test_tts = gTTS(text="test", lang=lang_code, slow=False)
                    tts = gTTS(text=clean_text, lang=lang_code, slow=False)
                except Exception as lang_error:
                    logger.warning(f"Language {lang_code} not fully supported, falling back to English: {lang_error}")
                    tts = gTTS(text=clean_text, lang='en', slow=False)
            else:
                tts = gTTS(text=clean_text, lang=lang_code, slow=False)
            
            tts.save(audio_path)
            
            return f"static/audio/{audio_filename}"
            
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
    
    def clean_text_for_tts(self, text: str) -> str:
        import re
        
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'`(.*?)`', r'\1', text)
        
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        if len(text) > 5000:
            text = text[:5000] + "..."
        
        return text
    
    def get_supported_languages(self) -> dict:
        return {
            'english': {
                'code': 'en',
                'name': 'English',
                'native_name': 'English'
            },
            'tamil': {
                'code': 'ta',
                'name': 'Tamil',
                'native_name': 'தமிழ்'
            },
            'hindi': {
                'code': 'hi',
                'name': 'Hindi',
                'native_name': 'हिन्दी'
            }
        }
    
    def delete_audio_file(self, audio_path: str) -> bool:
        try:
            full_path = os.path.join(self.static_folder.replace('static/', ''), audio_path.replace('static/', ''))
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting audio file: {e}")
            return False
    
    def cleanup_old_audio_files(self, max_age_hours: int = 24) -> int:
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            deleted_count = 0
            
            for filename in os.listdir(self.audio_folder):
                if filename.startswith('tts_') and filename.endswith('.mp3'):
                    file_path = os.path.join(self.audio_folder, filename)
                    file_age = current_time - os.path.getctime(file_path)
                    
                    if file_age > max_age_seconds:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Error deleting old audio file {filename}: {e}")
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error during audio cleanup: {e}")
            return 0
    
    def get_audio_duration(self, audio_path: str) -> float:
        try:
            file_size = os.path.getsize(audio_path)
            estimated_duration = file_size / 1024
            return min(estimated_duration, 300)
        except Exception as e:
            logger.error(f"Error getting audio duration: {e}")
            return 0.0
