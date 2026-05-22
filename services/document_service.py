import os
import PyPDF2
import docx
import logging
from werkzeug.utils import secure_filename
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self, upload_folder: str, allowed_extensions: set):
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        os.makedirs(upload_folder, exist_ok=True)
    
    def allowed_file(self, filename: str) -> bool:
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def save_file(self, file, user_id: int) -> Tuple[Optional[str], Optional[str]]:
        try:
            if file and self.allowed_file(file.filename):
                user_dir = os.path.join(self.upload_folder, str(user_id))
                os.makedirs(user_dir, exist_ok=True)
                
                filename = secure_filename(file.filename)
                
                import time
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{timestamp}{ext}"
                
                file_path = os.path.join(user_dir, filename)
                file.save(file_path)
                
                return filename, file_path
            return None, None
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None, None
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return f"Error reading PDF: {str(e)}"
    
    def extract_text_from_docx(self, file_path: str) -> str:
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {e}")
            return f"Error reading DOCX: {str(e)}"
    
    def extract_text_from_txt(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error extracting text from TXT: {e}")
            try:
                with open(file_path, 'r', encoding='latin-1') as file:
                    return file.read()
            except Exception as e2:
                logger.error(f"Error with fallback encoding: {e2}")
                return f"Error reading TXT: {str(e)}"
    
    def extract_text(self, file_path: str, file_type: str) -> str:
        try:
            if file_type.lower() == 'pdf':
                return self.extract_text_from_pdf(file_path)
            elif file_type.lower() == 'docx':
                return self.extract_text_from_docx(file_path)
            elif file_type.lower() == 'txt':
                return self.extract_text_from_txt(file_path)
            else:
                return f"Unsupported file type: {file_type}"
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return f"Error processing file: {str(e)}"
    
    def get_file_info(self, file) -> dict:
        try:
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            
            filename = file.filename
            file_type = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
            
            return {
                'size': size,
                'type': file_type,
                'name': filename
            }
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {
                'size': 0,
                'type': 'unknown',
                'name': 'unknown'
            }
    
    def delete_file(self, file_path: str) -> bool:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    def validate_legal_document(self, content: str) -> dict:
        validation_result = {
            'is_valid': True,
            'issues': [],
            'confidence': 'high'
        }
        
        if len(content.strip()) < 100:
            validation_result['issues'].append('Document appears too short for legal analysis')
            validation_result['confidence'] = 'low'
        
        legal_keywords = [
            'court', 'judge', 'law', 'legal', 'contract', 'agreement', 
            'whereas', 'therefore', 'hereby', 'jurisdiction', 'statute',
            'regulation', 'plaintiff', 'defendant', 'party', 'clause'
        ]
        
        content_lower = content.lower()
        found_keywords = sum(1 for keyword in legal_keywords if keyword in content_lower)
        
        if found_keywords < 3:
            validation_result['issues'].append('Document may not be legal in nature')
            validation_result['confidence'] = 'medium'
        
        structure_indicators = ['section', 'article', 'paragraph', 'subsection', 'chapter']
        found_structures = sum(1 for indicator in structure_indicators if indicator in content_lower)
        
        if found_structures == 0:
            validation_result['issues'].append('Document lacks typical legal structure')
            validation_result['confidence'] = 'medium'
        
        return validation_result
