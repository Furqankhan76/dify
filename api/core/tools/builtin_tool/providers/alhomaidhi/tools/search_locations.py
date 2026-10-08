import logging
import os
import re
from collections.abc import Generator
from typing import Any, override
from sqlalchemy.orm import Session

from core.tools.builtin_tool.tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

logger = logging.getLogger(__name__)

# Fallback flagship stores in major Saudi cities
DEFAULT_BRANCHES = [
    {
        "branch_name": "Al Nakheel Mall Branch (Riyadh)",
        "branch_name_ar": "فرع النخيل مول (الرياض)",
        "city": "Riyadh",
        "city_ar": "الرياض",
        "address": "Al Nakheel Mall, Northern Ring Branch Rd, Al Izdihar, Riyadh",
        "address_ar": "النخيل مول، الطريق الدائري الشمالي، حي الازدهار، الرياض",
        "timings": "9:30 AM - 11:00 PM (Daily)",
        "maps_url": "https://maps.google.com/?q=24.7681,46.7153",
    },
    {
        "branch_name": "Riyadh Park Mall Branch (Riyadh)",
        "branch_name_ar": "فرع الرياض بارك (الرياض)",
        "city": "Riyadh",
        "city_ar": "الرياض",
        "address": "Riyadh Park, Northern Ring Branch Rd, Al Aqiq, Riyadh",
        "address_ar": "الرياض بارك، الطريق الدائري الشمالي، حي العقيق، الرياض",
        "timings": "9:30 AM - 11:30 PM (Daily)",
        "maps_url": "https://maps.google.com/?q=24.7744,46.6298",
    },
    {
        "branch_name": "Mall of Arabia Branch (Jeddah)",
        "branch_name_ar": "فرع مجمع العرب (جدة)",
        "city": "Jeddah",
        "city_ar": "جدة",
        "address": "Mall of Arabia, Madinah Rd, An Nuzhah, Jeddah",
        "address_ar": "مجمع العرب، طريق المدينة، حي النزهة، جدة",
        "timings": "10:00 AM - 11:00 PM (Daily)",
        "maps_url": "https://maps.google.com/?q=21.6322,39.1558",
    },
    {
        "branch_name": "Red Sea Mall Branch (Jeddah)",
        "branch_name_ar": "فرع رد سي مول (جدة)",
        "city": "Jeddah",
        "city_ar": "جدة",
        "address": "Red Sea Mall, King Abdul Aziz Rd, Ash Shati, Jeddah",
        "address_ar": "رد سي مول، طريق الملك عبدالعزيز، حي الشاطئ، جدة",
        "timings": "10:00 AM - 11:30 PM (Daily)",
        "maps_url": "https://maps.google.com/?q=21.6267,39.1105",
    },
    {
        "branch_name": "Dhahran Mall Branch (Dammam / Khobar)",
        "branch_name_ar": "فرع الظهران مول (الدمام / الخبر)",
        "city": "Dammam",
        "city_ar": "الدمام",
        "address": "Mall of Dhahran, King Saud Rd, Al Dawhah Al Janubiyah, Dhahran",
        "address_ar": "الظهران مول، طريق الملك سعود، الدوحة الجنوبية، الظهران",
        "timings": "9:30 AM - 11:00 PM (Daily)",
        "maps_url": "https://maps.google.com/?q=26.3075,50.1744",
    },
]


class SearchLocationsTool(BuiltinTool):
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
        query = str(tool_parameters.get("query", "")).strip()
        mongo_uri = os.getenv("MONGODB_URI", "")
        db_name = os.getenv("MONGODB_DB_NAME", "sundus_ai")

        results = []

        # 1. Try querying MongoDB if available
        if mongo_uri and MongoClient is not None:
            try:
                client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
                db = client[db_name]
                filter_q = {}
                if query:
                    regex_pat = re.compile(re.escape(query), re.IGNORECASE)
                    filter_q = {
                        "$or": [
                            {"location_title": {"$regex": regex_pat}},
                            {"location_title_ara": {"$regex": regex_pat}},
                            {"location_address": {"$regex": regex_pat}},
                            {"city": {"$regex": regex_pat}},
                            {"city_ara": {"$regex": regex_pat}},
                        ]
                    }
                cursor = db["locations"].find(filter_q).limit(5)
                for loc in cursor:
                    results.append({
                        "branch_name": loc.get("location_title", loc.get("title", "")),
                        "branch_name_ar": loc.get("location_title_ara", ""),
                        "address": loc.get("location_address", ""),
                        "timings": loc.get("timings", "9:30 AM - 11:00 PM"),
                        "maps_url": f"https://maps.google.com/?q={loc.get('location_latitude')},{loc.get('location_longitude')}" if loc.get("location_latitude") else None,
                    })
            except Exception as e:
                logger.warning(f"Failed to query locations from MongoDB: {str(e)}")

        # 2. Fallback to curated flagship branches matching query
        if not results:
            query_lower = query.lower()
            for b in DEFAULT_BRANCHES:
                if (
                    not query
                    or query_lower in b["city"].lower()
                    or query_lower in b["city_ar"]
                    or query_lower in b["branch_name"].lower()
                    or query in b["branch_name_ar"]
                ):
                    results.append(b)

        if not results:
            results = DEFAULT_BRANCHES[:3]

        yield self.create_json_message({
            "query": query,
            "branches": results,
            "count": len(results),
        })
