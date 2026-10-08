import logging
from flask import jsonify, request
from flask_restx import Resource

from controllers.web import web_ns
from services.aisensy.webhook_processor import WebhookProcessor

logger = logging.getLogger(__name__)
processor = WebhookProcessor()


@web_ns.route("/v1/aisensy/webhook", endpoint="aisensy_webhook_web")
class WebAISensyWebhookApi(Resource):
    @web_ns.doc("handle_aisensy_webhook_web", security=[])
    def post(self):
        """
        AISensy / Mock Server WhatsApp Webhook Endpoint.
        Accepts incoming WhatsApp message webhooks and processes them via Dify.
        """
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

    @web_ns.doc("verify_aisensy_webhook_web", security=[])
    def get(self):
        """Health check / verification endpoint for AISensy webhook."""
        return jsonify({"status": "active", "service": "AISensy WhatsApp Webhook Handler"}), 200
