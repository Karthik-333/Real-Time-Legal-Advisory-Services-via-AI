from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from . import db

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False, default='New Chat')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = db.relationship('Message', backref='chat', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'message_count': len(self.messages)
        }

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, nullable=False)
    language = db.Column(db.String(20), default='english')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    audio_file = db.Column(db.String(200))
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'is_user': self.is_user,
            'language': self.language,
            'timestamp': self.timestamp.isoformat(),
            'audio_file': self.audio_file
        }
