"""DB models — import all models here so Alembic can discover them via Base.metadata."""

from app.db.models.chat_feedback import ChatFeedback
from app.db.models.chat_query import ChatQuery
from app.db.models.chat_session import ChatSession
from app.db.models.document import Document
from app.db.models.firm import Firm
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.refresh_token import RefreshToken
from app.db.models.task_submission import TaskSubmission
from app.db.models.user import User

__all__ = [
    "ChatFeedback",
    "ChatQuery",
    "ChatSession",
    "Document",
    "Firm",
    "Matter",
    "MatterAccess",
    "RefreshToken",
    "TaskSubmission",
    "User",
]
