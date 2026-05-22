from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_models():
    from .user import User
    from .chat import Chat, Message
    from .document import Document
    return User, Chat, Message, Document

try:
    from .user import User
    from .chat import Chat, Message
    from .document import Document
except ImportError:
    User = None
    Chat = None
    Message = None
    Document = None
