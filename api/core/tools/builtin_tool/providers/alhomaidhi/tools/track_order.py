import logging
import os
from collections.abc import Generator
from typing import Any, override
import requests
from sqlalchemy.orm import Session

from core.tools.builtin_tool.tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage

logger = logging.getLogger(__name__)


class TrackOrderTool(BuiltinTool):
    @override
    def _invoke(
        self,
        session: Session,
        user_id: str,
        tool_parameters: dict[str, Any],
        conversation_id: str | None = None,
        app_id: str | None = None,
        message_id: str | None = None,
    ) -> Generator[ToolInvokeMessage, None, None]:
        order_id = tool_parameters.get("order_id", "")
        base_url = os.getenv("ALHOMAIDHI_API_BASE_URL", "https://alhomaidhigroup.smf.mybluehost.me/wp-json/alhomaidhi-api/v1").rstrip("/")
        api_key = os.getenv("ALHOMAIDHI_API_KEY", "Basic WVAwNkZCV1A4SzRDOjhLUzRHVTlZVTBRMlI1S1Q=")
        default_user_id = os.getenv("ALHOMAIDHI_DEFAULT_USER_ID", "102")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": api_key,
            "user_id": default_user_id,
            "Cookie": "pll_language=en",
        }

        try:
            url = f"{base_url}/list_orders"
            params = {}
            if order_id:
                params["order_id"] = order_id.replace("#", "")

            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                orders = data.get("message", [])
                if isinstance(orders, list) and orders:
                    latest = orders[0]
                    det = latest.get("order_details", {})
                    yield self.create_json_message({
                        "order_id": det.get("order_id"),
                        "status": det.get("order_status"),
                        "total": det.get("total"),
                        "placed_date": det.get("order_placed_date"),
                        "is_aramex": det.get("is_aramex_order"),
                    })
                    return
                else:
                    yield self.create_text_message("No order details found.")
                    return
            else:
                yield self.create_text_message(f"Order API status: {res.status_code}")
                return
        except Exception as e:
            logger.exception(f"Error tracking order: {str(e)}")
            yield self.create_text_message(f"Order tracking error: {str(e)}")
