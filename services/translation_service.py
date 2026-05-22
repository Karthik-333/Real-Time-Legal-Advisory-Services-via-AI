import logging
import requests
import json
from typing import Optional, Dict, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

class TranslationService:
    
    def __init__(self):
        self.supported_languages = {
            'english': 'en',
            'tamil': 'ta', 
            'hindi': 'hi'
        }
        
        self.language_names = {
            'english': 'English',
            'tamil': 'தமிழ்',
            'hindi': 'हिन्दी'
        }
    
    def translate_text(self, text: str, source_lang: str = 'english', target_lang: str = 'tamil') -> str:
        
        if source_lang == target_lang:
            return text
        
        if source_lang == target_lang:
            return text
            
        try:
            source_code = self.supported_languages.get(source_lang, 'en')
            target_code = self.supported_languages.get(target_lang, 'ta')
            
            translated = self._translate_with_mymemory(text, source_code, target_code)
            
            if translated:
                logger.info(f"Successfully translated text from {source_lang} to {target_lang}")
                return translated
                
            logger.warning(f"Translation failed, returning original text")
            return text
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text
    
    def _translate_with_mymemory(self, text: str, source_code: str, target_code: str) -> Optional[str]:
        try:
            if len(text) > 1000:
                text = text[:1000] + "..."
            
            encoded_text = quote(text)
            
            url = f"https://api.mymemory.translated.net/get?q={encoded_text}&langpair={source_code}|{target_code}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('responseStatus') == 200:
                    translated_text = data.get('responseData', {}).get('translatedText', '')
                    
                    if translated_text and translated_text.lower() != text.lower():
                        return translated_text
                        
            return None
            
        except Exception as e:
            logger.error(f"MyMemory translation error: {e}")
            return None
    
    def _translate_with_libre(self, text: str, source_code: str, target_code: str) -> Optional[str]:
        try:
            return None
            
        except Exception as e:
            logger.error(f"LibreTranslate error: {e}")
            return None
    
    def detect_language(self, text: str) -> str:
        try:
            if self._contains_tamil_chars(text):
                return 'tamil'
            elif self._contains_hindi_chars(text):
                return 'hindi'
            else:
                return 'english'
                
        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return 'english'
    
    def _contains_tamil_chars(self, text: str) -> bool:
        tamil_range = range(0x0B80, 0x0BFF)
        return any(ord(char) in tamil_range for char in text)
    
    def _contains_hindi_chars(self, text: str) -> bool:
        devanagari_range = range(0x0900, 0x097F)
        return any(ord(char) in devanagari_range for char in text)
    
    def get_supported_languages(self) -> Dict[str, str]:
        return self.language_names.copy()
    
    def is_language_supported(self, language: str) -> bool:
        return language in self.supported_languages
    
    def translate_legal_response(self, response: str, target_language: str) -> str:
        
        if target_language == 'english' or not self.is_language_supported(target_language):
            return response
        
        try:
            parts = response.split('\n\n')
            translated_parts = []
            
            for part in parts:
                if part.strip():
                    if part.startswith('**') or part.startswith('##') or part.startswith('- '):
                        translated_part = self._translate_with_formatting(part, 'english', target_language)
                        translated_parts.append(translated_part)
                    else:
                        translated_part = self.translate_text(part, 'english', target_language)
                        translated_parts.append(translated_part)
                else:
                    translated_parts.append(part)
            
            return '\n\n'.join(translated_parts)
            
        except Exception as e:
            logger.error(f"Legal response translation error: {e}")
            return response
    
    def _translate_with_formatting(self, text: str, source_lang: str, target_lang: str) -> str:
        try:
            original_text = text
            
            if text.startswith('**') and text.endswith('**'):
                inner_text = text[2:-2]
                translated_inner = self.translate_text(inner_text, source_lang, target_lang)
                return f"**{translated_inner}**"
            elif text.startswith('## '):
                inner_text = text[3:]
                translated_inner = self.translate_text(inner_text, source_lang, target_lang)
                return f"## {translated_inner}"
            elif text.startswith('- '):
                inner_text = text[2:]
                translated_inner = self.translate_text(inner_text, source_lang, target_lang)
                return f"- {translated_inner}"
            else:
                return self.translate_text(text, source_lang, target_lang)
                
        except Exception as e:
            logger.error(f"Formatting translation error: {e}")
            return text
