import logging
import os
import re
import time
from typing import Any, Dict, Optional
import requests

from services.aisensy.aisensy_sender import AISensySender
from services.aisensy.guardrails import Guardrails
from services.aisensy.mongo_storage import MongoStorage

logger = logging.getLogger(__name__)

GREETINGS = {
    # English
    "hi", "hello", "hey", "hola", "hi there", "hello there", "good morning", "good evening", "howdy", "morning", "evening",
    # Arabic
    "سلام", "هلا", "مرحبا", "حياك", "أهلا", "أهلين", "صباح الخير", "مساء الخير", "السلام عليكم", "يا هلا"
}


def is_arabic(text: str) -> bool:
    """Detect if text is primarily in Arabic (>30% Arabic characters)."""
    if not text:
        return False
    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    total_chars = len(re.sub(r"\s", "", text))
    if total_chars == 0:
        return False
    return (arabic_chars / total_chars) > 0.3


def is_simple_greeting(text: str) -> bool:
    """Check if the text is a simple greeting."""
    if not text:
        return False
    normalized = re.sub(r"[?!.,]", "", text.lower().strip())
    if normalized in GREETINGS:
        return True
    words = normalized.split()
    if len(words) == 1 and words[0] in GREETINGS:
        return True
    return False


class TextMessageHandler:
    """
    Handles WhatsApp TEXT messages for Dify.
    Mirrors sundus_ai_backend logic:
    - Language detection (AR / EN)
    - Guardrail check against prompt injection
    - MongoDB logging (sundus_ai database)
    - Instant acknowledgment for complex queries
    - Dify Agent execution
    - AISensy message dispatch with interactive feedback
    """

    def __init__(self, sender: Optional[AISensySender] = None, storage: Optional[MongoStorage] = None):
        self.sender = sender or AISensySender()
        self.storage = storage or MongoStorage()
        self.dify_api_url = os.getenv("DIFY_API_URL", "http://localhost:5001/v1").rstrip("/")
        self.dify_api_key = os.getenv("DIFY_API_KEY", "")

    def process(
        self,
        phone_number: str,
        message_id: str,
        text: str,
        conversation_id: Optional[str] = None,
        send_ack: bool = True,
    ) -> Dict[str, Any]:
        """Process incoming text message end-to-end."""
        start_time = time.time()
        user_lang = "ar" if is_arabic(text) else "en"

        # 1. Guardrail Check (Prompt Injection)
        injection_result = Guardrails.detect_prompt_injection(text)
        if injection_result.get("is_injection"):
            logger.warning(f"Blocked prompt injection attack from {phone_number}")
            refusal_msg = (
                "أنا مساعد ذكي لمجموعة الحميضي. يمكنني مساعدتك في الاستفسارات المتعلقة بالساعات وفروعنا وتتبع الطلبات فقط."
                if user_lang == "ar"
                else "I am an AI assistant for AlHomaidhi Group. I can only assist you with watches, store locations, and order tracking queries."
            )
            self.sender.send_text(phone_number, refusal_msg)
            self.storage.save_message(phone_number, message_id, "user", text, conversation_id)
            self.storage.save_message(phone_number, f"reply_{message_id}", "assistant", refusal_msg, conversation_id)
            return {"success": False, "reason": "prompt_injection_blocked"}

        # 2. Save User Message to MongoDB
        self.storage.save_message(phone_number, message_id, "user", text, conversation_id)

        # 3. Send Instant Acknowledgment if needed (matching sundus_ai_backend)
        if send_ack and not is_simple_greeting(text):
            ack_text = "جارٍ معالجة طلبك... ⏳" if user_lang == "ar" else "Processing your request... ⏳"
            self.sender.send_text(phone_number, ack_text)

        # 4. Call Dify Chat API
        dify_response = self._call_dify_agent(phone_number, text, conversation_id)
        reply_text = dify_response.get("answer", "")
        new_conversation_id = dify_response.get("conversation_id", conversation_id)

        if not reply_text:
            reply_text = (
                "شكراً لتواصلك مع مجموعة الحميضي. كيف يمكننا مساعدتك اليوم بخصوص ساعاتنا أو طلباتك؟"
                if user_lang == "ar"
                else "Thank you for reaching out to AlHomaidhi Group. How can we assist you with our watches or orders today?"
            )

        # 5. Send AI Reply via AISensy with interactive feedback
        feedback_prompt = "هل كان هذا الرد مفيداً؟" if user_lang == "ar" else "Was this response helpful?"
        feedback_buttons = (
            [{"id": "feedback_yes", "title": "نعم 👍"}, {"id": "feedback_no", "title": "لا 👎"}]
            if user_lang == "ar"
            else [{"id": "feedback_yes", "title": "Yes 👍"}, {"id": "feedback_no", "title": "No 👎"}]
        )

        send_res = self.sender.send_text(phone_number, reply_text)
        if send_res.get("success"):
            self.sender.send_interactive(phone_number, feedback_prompt, feedback_buttons)

        reply_msg_id = send_res.get("message_id") or f"reply_{message_id}"

        # 6. Save Assistant Reply to MongoDB
        proc_time_ms = int((time.time() - start_time) * 1000)
        metadata = {
            "processing_time_ms": proc_time_ms,
            "dify_conversation_id": new_conversation_id,
            "should_send_feedback": True,
            "language": user_lang,
        }
        self.storage.save_message(
            phone_number=phone_number,
            message_id=reply_msg_id,
            role="assistant",
            content=reply_text,
            conversation_id=new_conversation_id,
            replied_to_message_id=message_id,
            metadata=metadata,
        )

        return {
            "success": True,
            "reply_text": reply_text,
            "conversation_id": new_conversation_id,
            "processing_time_ms": proc_time_ms,
        }

    def _call_dify_agent(self, phone_number: str, text: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Call Dify API `/v1/chat-messages` endpoint supporting Agent streaming."""
        url = f"{self.dify_api_url}/chat-messages"
        headers = {
            "Authorization": f"Bearer {self.dify_api_key}",
            "Content-Type": "application/json",
        }
        clean_phone = phone_number.replace("+", "").strip()
        payload = {
            "inputs": {},
            "query": text,
            "response_mode": "streaming",
            "user": clean_phone,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            import json
            res = requests.post(url, json=payload, headers=headers, stream=True, timeout=45)
            if res.status_code != 200:
                logger.error(f"Dify Chat API returned status {res.status_code}: {res.text}")
                return {"answer": "", "conversation_id": conversation_id}

            agent_answer = ""
            standard_answer = ""
            has_agent_msg = False
            ret_conv_id = conversation_id

            for raw_line in res.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line[5:].strip())
                    event = data.get("event")
                    if data.get("conversation_id"):
                        ret_conv_id = data.get("conversation_id")
                    if event == "agent_message":
                        has_agent_msg = True
                        agent_answer += data.get("answer", "")
                    elif event == "message":
                        standard_answer += data.get("answer", "")
                except Exception:
                    pass

            final_answer = (agent_answer if has_agent_msg else standard_answer).strip()
            return {
                "answer": final_answer,
                "conversation_id": ret_conv_id,
            }
        except Exception as e:
            logger.exception(f"Exception calling Dify Chat API: {str(e)}")
            return {"answer": "", "conversation_id": conversation_id}


