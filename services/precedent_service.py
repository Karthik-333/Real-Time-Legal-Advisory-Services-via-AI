import json
import logging
from typing import List, Dict, Any
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class PrecedentService:
    def __init__(self, precedents_file: str):
        self.precedents_file = precedents_file
        self.precedents = self.load_precedents()
    
    def load_precedents(self) -> List[Dict[str, Any]]:
        try:
            with open(self.precedents_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Precedents file not found: {self.precedents_file}")
            return self.create_default_precedents()
        except json.JSONDecodeError:
            logger.error(f"Error parsing precedents file: {self.precedents_file}")
            return self.create_default_precedents()
    
    def create_default_precedents(self) -> List[Dict[str, Any]]:
        default_precedents = [
            {
                "id": 1,
                "case_name": "Kesavananda Bharati v. State of Kerala",
                "year": 1973,
                "court": "Supreme Court of India",
                "jurisdiction": "India",
                "citation": "AIR 1973 SC 1461",
                "legal_area": "Constitutional Law",
                "keywords": ["basic structure", "constitutional amendment", "judicial review", "parliamentary supremacy"],
                "summary": "Established the basic structure doctrine limiting Parliament's power to amend the Constitution.",
                "importance": "Landmark",
                "url": "https://indiankanoon.org/doc/257876/"
            },
            {
                "id": 2,
                "case_name": "Maneka Gandhi v. Union of India",
                "year": 1978,
                "court": "Supreme Court of India",
                "jurisdiction": "India",
                "citation": "AIR 1978 SC 597",
                "legal_area": "Constitutional Law",
                "keywords": ["fundamental rights", "personal liberty", "due process", "article 21"],
                "summary": "Expanded Article 21 to include due process requirements for any law affecting personal liberty.",
                "importance": "Landmark",
                "url": "https://indiankanoon.org/doc/1766147/"
            },
            {
                "id": 3,
                "case_name": "Vishaka v. State of Rajasthan",
                "year": 1997,
                "court": "Supreme Court of India",
                "jurisdiction": "India",
                "citation": "AIR 1997 SC 3011",
                "legal_area": "Women's Rights",
                "keywords": ["sexual harassment", "workplace", "women's rights", "guidelines"],
                "summary": "Laid down comprehensive guidelines to prevent sexual harassment of women at workplaces.",
                "importance": "Landmark",
                "url": "https://indiankanoon.org/doc/1031794/"
            },
            {
                "id": 4,
                "case_name": "K.S. Puttaswamy v. Union of India",
                "year": 2017,
                "court": "Supreme Court of India",
                "jurisdiction": "India",
                "citation": "(2017) 10 SCC 1",
                "legal_area": "Constitutional Law",
                "keywords": ["right to privacy", "fundamental right", "article 21", "data protection"],
                "summary": "Declared the right to privacy as a fundamental right under Article 21.",
                "importance": "Landmark",
                "url": "https://indiankanoon.org/doc/127517806/"
            },
            {
                "id": 5,
                "case_name": "D.K. Basu v. State of West Bengal",
                "year": 1997,
                "court": "Supreme Court of India",
                "jurisdiction": "India",
                "citation": "AIR 1997 SC 610",
                "legal_area": "Criminal Law",
                "keywords": ["custodial death", "torture", "arrest guidelines", "human rights"],
                "summary": "Laid down 11 mandatory guidelines to prevent custodial violence and torture.",
                "importance": "Landmark",
                "url": "https://indiankanoon.org/doc/501198/"
            }
        ]
        
        try:
            import os
            os.makedirs(os.path.dirname(self.precedents_file), exist_ok=True)
            with open(self.precedents_file, 'w', encoding='utf-8') as f:
                json.dump(default_precedents, f, indent=2, ensure_ascii=False)
            logger.info("Created default precedents file")
        except Exception as e:
            logger.error(f"Error creating default precedents file: {e}")
        
        return default_precedents
    
    def find_similar_precedents(self, query_text: str, legal_area: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            query_keywords = self.extract_keywords(query_text.lower())
            matched_precedents = []
            
            for precedent in self.precedents:
                score = self.calculate_similarity_score(query_keywords, precedent, legal_area)
                if score > 0:
                    precedent_copy = precedent.copy()
                    precedent_copy['similarity_score'] = score
                    matched_precedents.append(precedent_copy)
            
            matched_precedents.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return matched_precedents[:limit]
        
        except Exception as e:
            logger.error(f"Error finding similar precedents: {e}")
            return []
    
    def extract_keywords(self, text: str) -> List[str]:
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these', 'those'
        }
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [word for word in words if word not in stop_words]
        
        return list(set(keywords))
    
    def calculate_similarity_score(self, query_keywords: List[str], precedent: Dict[str, Any], legal_area: str = None) -> float:
        score = 0.0
        
        if legal_area and precedent.get('legal_area', '').lower() == legal_area.lower():
            score += 2.0
        
        precedent_keywords = precedent.get('keywords', [])
        precedent_text = (
            f"{precedent.get('case_name', '')} "
            f"{precedent.get('summary', '')} "
            f"{' '.join(precedent_keywords)}"
        ).lower()
        
        precedent_words = self.extract_keywords(precedent_text)
        
        common_keywords = set(query_keywords) & set(precedent_words)
        if len(query_keywords) > 0:
            keyword_score = len(common_keywords) / len(query_keywords)
            score += keyword_score * 3.0
        
        if precedent.get('importance') == 'Landmark':
            score += 0.5
        
        current_year = datetime.now().year
        case_year = precedent.get('year', 1800)
        if current_year - case_year < 50:
            score += 0.3
        
        return round(score, 2)
    
    def get_precedent_by_id(self, precedent_id: int) -> Dict[str, Any]:
        for precedent in self.precedents:
            if precedent.get('id') == precedent_id:
                return precedent
        return {}
    
    def search_by_citation(self, citation: str) -> Dict[str, Any]:
        for precedent in self.precedents:
            if citation.lower() in precedent.get('citation', '').lower():
                return precedent
        return {}
    
    def get_precedents_by_area(self, legal_area: str) -> List[Dict[str, Any]]:
        return [p for p in self.precedents if p.get('legal_area', '').lower() == legal_area.lower()]
    
    def add_precedent(self, precedent_data: Dict[str, Any]) -> bool:
        try:
            max_id = max([p.get('id', 0) for p in self.precedents], default=0)
            precedent_data['id'] = max_id + 1
            
            self.precedents.append(precedent_data)
            
            with open(self.precedents_file, 'w', encoding='utf-8') as f:
                json.dump(self.precedents, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"Error adding precedent: {e}")
            return False
    
    def format_precedent_for_display(self, precedent: Dict[str, Any]) -> str:
        if not precedent:
            return "No precedent information available."

        formatted = f"""**{precedent.get('case_name', 'Unknown Case')}** ({precedent.get('year', 'N/A')})

**Court:** {precedent.get('court', 'N/A')}
**Citation:** {precedent.get('citation', 'N/A')}
**Legal Area:** {precedent.get('legal_area', 'N/A')}

**Summary:** {precedent.get('summary', 'No summary available.')}

**Keywords:** {', '.join(precedent.get('keywords', []))}

**Similarity Score:** {precedent.get('similarity_score', 'N/A')}"""
        
        return formatted
