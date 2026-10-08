import logging
from flask import jsonify, request
from flask_restx import Resource

from controllers.service_api import bp, service_api_ns
from services.aisensy.webhook_processor import WebhookProcessor

logger = logging.getLogger(__name__)
processor = WebhookProcessor()


@bp.route("/aisensy/webhook", methods=["GET", "POST"])
def handle_aisensy_webhook_bp():
    """Blueprint handler for AISensy webhook."""
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


@service_api_ns.route("/aisensy/webhook", endpoint="aisensy_webhook")
class AISensyWebhookApi(Resource):
    @service_api_ns.doc("handle_aisensy_webhook", security=[])
    def post(self):
        """
        AISensy / Mock Server WhatsApp Webhook Endpoint.
        Accepts incoming WhatsApp message webhooks and processes them via Dify.
        """
        return handle_aisensy_webhook_bp()

    @service_api_ns.doc("verify_aisensy_webhook", security=[])
    def get(self):
        """Health check / verification endpoint for AISensy webhook."""
        return handle_aisensy_webhook_bp()
