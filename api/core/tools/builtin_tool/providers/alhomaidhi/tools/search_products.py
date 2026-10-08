import json
import logging
import os
from collections.abc import Generator
from typing import Any, override
import requests
from sqlalchemy.orm import Session

from core.tools.builtin_tool.tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage

logger = logging.getLogger(__name__)


class SearchProductsTool(BuiltinTool):
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
        query = tool_parameters.get("query", "")
        base_url = os.getenv("ALHOMAIDHI_API_BASE_URL", "https://alhomaidhigroup.com/wp-json/alhomaidhiapp/v2").rstrip("/")
        api_key = os.getenv("ALHOMAIDHI_API_KEY", "550699352X72qodSOlbkS6exhCg4KM8ACjJkg3ZKz2Y6138rjtXG47XNSoM")
        default_user_id = os.getenv("ALHOMAIDHI_DEFAULT_USER_ID", "66")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": api_key,
            "user_id": str(default_user_id),
            "Cookie": "pll_language=en",
        }

        try:
            url = f"{base_url}/list_products"
            params = {"per_page": 5}
            if query:
                params["search"] = query
            res = requests.get(url, headers=headers, params=params, timeout=12)
            if res.status_code == 200:
                data = res.json()
                products = data.get("message", [])
                if isinstance(products, list) and products:
                    formatted = []
                    for p in products[:5]:
                        details = p.get("product_details", {})
                        images = p.get("images", [])
                        brands = p.get("brands", [])
                        img_src = images[0].get("src") if images else None
                        brand_name = brands[0].get("name") if brands else None
                        formatted.append({
                            "product_id": details.get("product_id"),
                            "name": details.get("name"),
                            "price": details.get("price"),
                            "regular_price": details.get("regular_price"),
                            "sku": details.get("sku"),
                            "stock_status": details.get("stock_status"),
                            "brand": brand_name,
                            "image_url": img_src,
                            "short_description": details.get("short_description"),
                        })
                    yield self.create_json_message({"products": formatted, "count": len(formatted)})
                    return
                else:
                    yield self.create_text_message(f"No products found matching '{query}'.")
                    return
            else:
                yield self.create_text_message(f"Product API returned status code {res.status_code}")
                return
        except Exception as e:
            logger.exception(f"Error executing search_products: {str(e)}")
            yield self.create_text_message(f"Failed to search products: {str(e)}")

