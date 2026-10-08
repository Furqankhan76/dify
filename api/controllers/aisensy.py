import logging
from flask import Blueprint, jsonify, request
from services.aisensy.webhook_processor import WebhookProcessor

logger = logging.getLogger(__name__)
bp = Blueprint("aisensy", __name__, url_prefix="/v1")
processor = WebhookProcessor()


@bp.route("/aisensy/webhook", methods=["GET", "POST"])
def handle_aisensy_webhook():
    """
    AISensy / Mock Server WhatsApp Webhook Endpoint.
    Receives incoming WhatsApp webhooks and processes them via Dify.
    """
    if request.method == "GET":
        return jsonify({"status": "active", "service": "AISensy WhatsApp Webhook Handler"}), 200

    try:
        payload = request.get_json(force=True, silent=True) or {}
        if not payload:
            payload = request.form.to_dict() or {}

        logger.info(f"Received AISensy webhook request: {payload}")
        result = processor.process_webhook(payload)
        return jsonify(result), 200
    except Exception as e:
        logger.exception(f"Error handling AISensy webhook: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
