import datetime
import logging
import os
from typing import Any, Dict, List, Optional
try:
    from pymongo import MongoClient, DESCENDING
except ImportError:
    MongoClient = None
    DESCENDING = -1

logger = logging.getLogger(__name__)


class MongoStorage:
    """
    MongoDB persistence service for WhatsApp conversations and feedback.
    Stores messages and feedback in `sundus_ai` database so `sundus_ai_backend` admin panel reads them seamlessly.
    """

    def __init__(self, uri: Optional[str] = None):
        self.uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017/sundus_ai")
        self.db_name = os.getenv("MONGODB_DB_NAME", "sundus_ai")
        self._client = None
        self._db = None

    def _get_db(self):
        if self._db is not None:
            return self._db
        if MongoClient is None:
            logger.error("pymongo module not installed. MongoDB operations will be skipped.")
            return None
        try:
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self._db = self._client[self.db_name]
            return self._db
        except Exception as e:
            logger.exception(f"Failed to connect to MongoDB at {self.uri}: {str(e)}")
            return None

    def save_message(
        self,
        phone_number: str,
        message_id: str,
        role: str,
        content: str,
        conversation_id: Optional[str] = None,
        replied_to_message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Save user or assistant message to `conversation_messages` collection."""
        db = self._get_db()
        if db is None:
            return False

        try:
            doc = {
                "phone_number": phone_number,
                "message_id": message_id,
                "role": role,
                "content": content,
                "conversation_id": conversation_id,
                "replied_to_message_id": replied_to_message_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "metadata": metadata or {},
            }
            db["conversation_messages"].insert_one(doc)
            logger.info(f"Saved {role} message [{message_id}] for {phone_number} to MongoDB")
            return True
        except Exception as e:
            logger.exception(f"Error saving message to MongoDB: {str(e)}")
            return False

    def get_recent_messages(self, phone_number: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch last `limit` messages for user chat context."""
        db = self._get_db()
        if db is None:
            return []

        try:
            cursor = (
                db["conversation_messages"]
                .find({"phone_number": phone_number})
                .sort("timestamp", DESCENDING)
                .limit(limit)
            )
            messages = list(cursor)
            messages.reverse()  # Return in chronological order
            return messages
        except Exception as e:
            logger.exception(f"Error fetching recent messages from MongoDB: {str(e)}")
            return []

    def save_feedback(
        self,
        phone_number: str,
        message_id: str,
        feedback_val: str,
        conversation_id: Optional[str] = None,
        original_message_id: Optional[str] = None,
        template_name: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bool:
        """Save feedback (yes/no) to `feedbacks` collection."""
        db = self._get_db()
        if db is None:
            return False

        try:
            is_pos = feedback_val.lower() == "yes"
            doc = {
                "phone_number": phone_number,
                "message_id": message_id,
                "original_message_id": original_message_id,
                "conversation_id": conversation_id,
                "feedback": feedback_val,
                "response_type": "positive" if is_pos else "escalation",
                "is_positive": is_pos,
                "template_name": template_name,
                "language": language,
                "created_at": datetime.datetime.now(datetime.timezone.utc),
            }
            db["feedbacks"].insert_one(doc)

            # Update original message metadata if present
            if original_message_id:
                db["conversation_messages"].update_one(
                    {"message_id": original_message_id},
                    {"$set": {"metadata.feedback": feedback_val, "metadata.was_helpful": is_pos}},
                )

            logger.info(f"Saved feedback [{feedback_val}] from {phone_number} to MongoDB")
            return True
        except Exception as e:
            logger.exception(f"Error saving feedback to MongoDB: {str(e)}")
            return False
