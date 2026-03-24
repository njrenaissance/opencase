"""DB models — import all models here so Alembic can discover them via Base.metadata."""

from app.db.models.document import Document
from app.db.models.firm import Firm
from app.db.models.matter import Matter
from app.db.models.matter_access import MatterAccess
from app.db.models.prompt import Prompt
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User

__all__ = [
    "Document",
    "Firm",
    "Matter",
    "MatterAccess",
    "Prompt",
    "RefreshToken",
    "User",
]
