from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from . import db

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    content_text = db.Column(db.Text)
    summary = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed = db.Column(db.Boolean, default=False)
    
    document_type = db.Column(db.String(100))
    jurisdiction = db.Column(db.String(100))
    case_number = db.Column(db.String(100))
    court = db.Column(db.String(200))
    judgment_date = db.Column(db.Date)
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'summary': self.summary,
            'uploaded_at': self.uploaded_at.isoformat(),
            'processed': self.processed,
            'document_type': self.document_type,
            'jurisdiction': self.jurisdiction,
            'case_number': self.case_number,
            'court': self.court,
            'judgment_date': self.judgment_date.isoformat() if self.judgment_date else None
        }
