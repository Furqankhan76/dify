import logging
import re
from typing import Any, Dict, Optional

from services.aisensy.aisensy_sender import AISensySender
from services.aisensy.mongo_storage import MongoStorage

logger = logging.getLogger(__name__)


def is_arabic(text: str) -> bool:
    """Detect if text is primarily Arabic."""
    if not text:
        return False
    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    total_chars = len(re.sub(r"\s", "", text))
    return total_chars > 0 and (arabic_chars / total_chars) > 0.3


class QuickReplyHandler:
    """
    Handles WhatsApp QUICK_REPLY interactive button clicks (e.g. Yes/No feedback).
    Mirrors sundus_ai_backend feedback processing and customer support escalation.
    """

    def __init__(self, sender: Optional[AISensySender] = None, storage: Optional[MongoStorage] = None):
        self.sender = sender or AISensySender()
        self.storage = storage or MongoStorage()

    def process(
        self,
        phone_number: str,
        message_id: str,
        btn_payload: str,
        btn_text: str,
        conversation_id: Optional[str] = None,
        original_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process interactive quick reply click."""
        payload_lower = (btn_payload or btn_text or "").lower()
        user_lang = "ar" if (is_arabic(btn_payload) or is_arabic(btn_text)) else "en"

        is_yes = any(k in payload_lower for k in ("yes", "feedback_yes", "نعم", "مفيد"))
        is_no = any(k in payload_lower for k in ("no", "feedback_no", "لا", "غير مفيد"))

        if is_yes or is_no:
            val = "yes" if is_yes else "no"
            self.storage.save_feedback(
                phone_number=phone_number,
                message_id=message_id,
                feedback_val=val,
                conversation_id=conversation_id,
                original_message_id=original_message_id,
                language=user_lang,
            )

            if is_yes:
                reply_text = (
                    "شكراً لتقييمك! نسعد بخدمتك دائماً. 😊"
                    if user_lang == "ar"
                    else "Thank you for your feedback! We're glad we could help. 😊"
                )
            else:
                reply_text = (
                    "نعتذر عن عدم تلبية توقعاتك. للحصول على مساعدة مباشرة، يمكنك التواصل مع فريق الدعم على الرقم: +966 9200 09339. 📞"
                    if user_lang == "ar"
                    else "We apologize that the response didn't meet your expectations. For further assistance, you can contact our support team at +966 9200 09339. 📞"
                )

            self.sender.send_text(phone_number, reply_text)
            return {"success": True, "type": "feedback", "value": val, "language": user_lang}
        else:
            # Generic quick reply
            reply_text = f"Received: {btn_text or btn_payload}"
            self.sender.send_text(phone_number, reply_text)
            return {"success": True, "type": "generic"}

