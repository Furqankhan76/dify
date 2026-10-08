import logging
import time
import uuid
from typing import Any, Dict, Optional

from services.aisensy.handlers.quick_reply_handler import QuickReplyHandler
from services.aisensy.handlers.text_handler import TextMessageHandler

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Main AISensy / Mock Server webhook payload processor.
    Handles both direct JSON payloads and official AI Sensy nested event payloads (`data.message`).
    """

    def __init__(self):
        self.text_handler = TextMessageHandler()
        self.quick_reply_handler = QuickReplyHandler()

    def process_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook payload from AI Sensy or Mock Server."""
        logger.info(f"Processing webhook payload: {payload}")

        # Handle nested AI Sensy payload format (data.message)
        msg_obj = payload.get("data", {}).get("message", {}) if isinstance(payload.get("data"), dict) else {}

        # Extract phone number
        phone_number = (
            payload.get("phone_number")
            or msg_obj.get("phone_number")
            or payload.get("wa_id")
            or msg_obj.get("contact_id")
            or payload.get("mobile_number")
            or payload.get("from")
            or payload.get("phone")
            or ""
        )

        message_type = (
            payload.get("message_type")
            or msg_obj.get("message_type")
            or payload.get("type")
            or "TEXT"
        ).upper()

        message_id = (
            payload.get("message_id")
            or msg_obj.get("id")
            or payload.get("id")
            or f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        )

        if not phone_number:
            logger.error("Missing phone number in webhook payload")
            return {"success": False, "error": "Missing phone_number in payload"}

        # Extract text content
        msg_content = msg_obj.get("message_content", {}) if isinstance(msg_obj.get("message_content"), dict) else {}
        text = (
            payload.get("text")
            or msg_content.get("text")
            or payload.get("message")
            or payload.get("content")
            or ""
        )
        if isinstance(text, dict):
            text = text.get("body", "")

        # Route by message type
        if message_type in ("TEXT", "MESSAGE"):
            return self.text_handler.process(
                phone_number=str(phone_number),
                message_id=str(message_id),
                text=str(text),
            )

        elif message_type in ("QUICK_REPLY", "BUTTON_REPLY", "INTERACTIVE"):
            btn_payload = (
                payload.get("callbackPayload")
                or msg_content.get("callbackPayload")
                or payload.get("payload")
                or ""
            )
            btn_text = (
                payload.get("text")
                or msg_content.get("text")
                or payload.get("title")
                or ""
            )
            original_msg_id = (
                payload.get("contextMessageId")
                or msg_obj.get("context", {}).get("id") if isinstance(msg_obj.get("context"), dict) else None
            )

            return self.quick_reply_handler.process(
                phone_number=str(phone_number),
                message_id=str(message_id),
                btn_payload=str(btn_payload),
                btn_text=str(btn_text),
                original_message_id=str(original_msg_id) if original_msg_id else None,
            )

        else:
            # Fallback for unsupported media types
            fallback_text = str(text) or f"[{message_type} received]"
            return self.text_handler.process(
                phone_number=str(phone_number),
                message_id=str(message_id),
                text=fallback_text,
            )
