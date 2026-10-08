import logging
import os
import re
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class AISensySender:
    """
    AISensy WhatsApp API Service for Dify Backend.
    Sends text, media, interactive buttons, and template messages via AISensy.
    """

    def __init__(self, api_key: Optional[str] = None, project_id: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("AISENSY_API_KEY", "")
        self.project_id = project_id or os.getenv("AISENSY_PROJECT_ID", "")
        self.base_url = (base_url or os.getenv("AISENSY_API_BASE_URL", "https://backend.aisensy.com")).rstrip("/")

        if not self.api_key or not self.project_id:
            logger.warning("AISensy credentials missing: AISENSY_API_KEY or AISENSY_PROJECT_ID not set.")

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-AiSensy-Project-API-Pwd": self.api_key,
        })

    def _format_phone(self, phone: str) -> str:
        """Sanitize phone number to contain digits only."""
        cleaned = re.sub(r"\D", "", str(phone or ""))
        return cleaned

    def _get_endpoint(self) -> str:
        return f"{self.base_url}/project-apis/v1/project/{self.project_id}/messages"

    def _send_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Post payload to AISensy API endpoint with error handling."""
        if not self.api_key or not self.project_id:
            logger.error("Cannot send AISensy message: Missing API key or Project ID.")
            return {"success": False, "error": "AISensy API key or Project ID missing"}

        url = self._get_endpoint()
        try:
            response = self.session.post(url, json=payload, timeout=15)
            response_json = response.json() if response.text else {}

            if response.status_code >= 400 or "errors" in response_json:
                err_msg = response_json.get("errors", response_json.get("message", response.text))
                logger.error(f"AISensy API error [{response.status_code}]: {err_msg}")
                return {
                    "success": False,
                    "status": response.status_code,
                    "error": str(err_msg),
                    "raw": response_json,
                }

            message_id = None
            if "messages" in response_json and len(response_json["messages"]) > 0:
                message_id = response_json["messages"][0].get("id")

            return {
                "success": True,
                "status": response.status_code,
                "message_id": message_id,
                "raw": response_json,
            }
        except Exception as e:
            logger.exception(f"AISensy request exception: {str(e)}")
            return {"success": False, "error": str(e)}

    def send_text(self, phone: str, text: str) -> Dict[str, Any]:
        """Send a plain text message via WhatsApp."""
        phone_num = self._format_phone(phone)
        payload = {
            "to": phone_num,
            "type": "text",
            "recipient_type": "individual",
            "text": {"body": text},
        }
        logger.info(f"Sending AISensy text message to {phone_num}")
        return self._send_payload(payload)

    def send_image(self, phone: str, image_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """Send an image message with optional caption."""
        phone_num = self._format_phone(phone)
        image_obj: Dict[str, Any] = {"link": image_url}
        if caption:
            image_obj["caption"] = caption

        payload = {
            "to": phone_num,
            "type": "image",
            "recipient_type": "individual",
            "image": image_obj,
        }
        return self._send_payload(payload)

    def send_audio(self, phone: str, audio_url: str) -> Dict[str, Any]:
        """Send an audio voice note message."""
        phone_num = self._format_phone(phone)
        payload = {
            "to": phone_num,
            "type": "audio",
            "recipient_type": "individual",
            "audio": {"link": audio_url},
        }
        return self._send_payload(payload)

    def send_document(self, phone: str, document_url: str, filename: Optional[str] = None, caption: Optional[str] = None) -> Dict[str, Any]:
        """Send a document (PDF, docx, etc.)."""
        phone_num = self._format_phone(phone)
        doc_obj: Dict[str, Any] = {"link": document_url}
        if filename:
            doc_obj["filename"] = filename
        if caption:
            doc_obj["caption"] = caption

        payload = {
            "to": phone_num,
            "type": "document",
            "recipient_type": "individual",
            "document": doc_obj,
        }
        return self._send_payload(payload)

    def send_interactive(self, phone: str, body_text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Send interactive quick-reply buttons (up to 3 buttons).
        Each button in `buttons` list: {"id": "btn_1", "title": "Yes"}
        """
        phone_num = self._format_phone(phone)
        action_buttons = []
        for btn in buttons[:3]:  # WhatsApp max 3 buttons
            action_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("id", btn.get("payload", "")),
                    "title": btn.get("title", btn.get("text", "")),
                },
            })

        payload = {
            "to": phone_num,
            "type": "interactive",
            "recipient_type": "individual",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": action_buttons},
            },
        }
        return self._send_payload(payload)

    def send_message_with_feedback(self, phone: str, text: str) -> Dict[str, Any]:
        """Send main text answer followed by a quick feedback interactive prompt."""
        res = self.send_text(phone, text)
        if not res.get("success"):
            return res

        buttons = [
            {"id": "feedback_yes", "title": "Yes 👍"},
            {"id": "feedback_no", "title": "No 👎"},
        ]
        return self.send_interactive(phone, "Was this response helpful?", buttons)

    def send_template(
        self,
        phone: str,
        template_name: str,
        language_code: str = "en_us",
        components: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send a WhatsApp Business HSM Template message."""
        phone_num = self._format_phone(phone)
        payload = {
            "to": phone_num,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }
        return self._send_payload(payload)

    def send_product_template(
        self,
        phone: str,
        template_name: str,
        language_code: str,
        image_url: str,
        product_name: str,
        sku: str,
        price: str,
        product_slug: str,
    ) -> Dict[str, Any]:
        """Send a pre-configured product card template with image header and product fields."""
        components = [
            {
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": image_url}}],
            },
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": product_name},
                    {"type": "text", "text": sku},
                    {"type": "text", "text": price},
                ],
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": 0,
                "parameters": [{"type": "text", "text": product_slug}],
            },
        ]
        return self.send_template(phone, template_name, language_code, components)

    def get_message_details(self, message_id: str) -> Dict[str, Any]:
        """Query status of a specific message ID."""
        if not self.api_key or not self.project_id:
            return {"success": False, "error": "AISensy API key missing"}

        url = f"{self.base_url}/project-apis/v1/project/{self.project_id}/messages/{message_id}"
        try:
            response = self.session.get(url, timeout=10)
            return {"success": True, "status": response.status_code, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}
