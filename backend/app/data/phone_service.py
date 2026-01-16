"""
Phone database service for querying and filtering phones.
"""
import json
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class PhoneService:
    def __init__(self):
        data_path = Path(__file__).parent / "phones.json"
        logger.info(f"Loading phone database from: {data_path}")
        with open(data_path, "r") as f:
            data = json.load(f)
        self.phones = data["phones"]
        self.brands = data["brands"]
        self.price_ranges = data["price_ranges"]
        self.features = data["features"]
        logger.info(f"Loaded {len(self.phones)} phones, {len(self.brands)} brands")

    def get_all_phones(self) -> list[dict]:
        """Get all phones in the database."""
        return self.phones

    def get_phone_by_id(self, phone_id: str) -> Optional[dict]:
        """Get a specific phone by its ID."""
        for phone in self.phones:
            if phone["id"] == phone_id:
                return phone
        return None

    def get_phone_by_name(self, name: str) -> Optional[dict]:
        """Get a phone by name (prefers exact match, then fuzzy match)."""
        name_lower = name.lower().strip()

        # First try exact match
        for phone in self.phones:
            if phone["name"].lower() == name_lower:
                return phone

        # Then try fuzzy match (substring)
        # Sort by name length to prefer shorter/more specific matches
        candidates = []
        for phone in self.phones:
            if name_lower in phone["name"].lower():
                candidates.append(phone)

        if candidates:
            # Return the one with shortest name (most specific match)
            candidates.sort(key=lambda p: len(p["name"]))
            return candidates[0]

        return None

    def search_phones(
        self,
        query: Optional[str] = None,
        brand: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_ram: Optional[int] = None,
        has_5g: Optional[bool] = None,
        min_battery: Optional[int] = None,
        min_refresh_rate: Optional[int] = None,
        has_ois: Optional[bool] = None,
        limit: int = 10
    ) -> list[dict]:
        """
        Search phones with various filters.
        """
        logger.debug(f"Searching phones - query: {query}, brand: {brand}, price: {min_price}-{max_price}")
        results = self.phones.copy()

        # Filter by brand
        if brand:
            brand_lower = brand.lower()
            results = [p for p in results if p["brand"].lower() == brand_lower]

        # Filter by price range
        if min_price is not None:
            results = [p for p in results if p["price"] >= min_price]
        if max_price is not None:
            results = [p for p in results if p["price"] <= max_price]

        # Filter by RAM
        if min_ram is not None:
            results = [p for p in results if p["ram"] >= min_ram]

        # Filter by 5G
        if has_5g is not None:
            results = [p for p in results if p["5g"] == has_5g]

        # Filter by battery capacity
        if min_battery is not None:
            results = [p for p in results if p["battery"]["capacity"] >= min_battery]

        # Filter by refresh rate
        if min_refresh_rate is not None:
            results = [p for p in results if p["display"]["refresh_rate"] >= min_refresh_rate]

        # Filter by OIS
        if has_ois is not None:
            results = [
                p for p in results
                if ("OIS" in p["camera"].get("features", [])) == has_ois
            ]

        # Text search in name, highlights, and features
        if query:
            query_lower = query.lower()
            scored_results = []
            for phone in results:
                score = 0
                # Name match
                if query_lower in phone["name"].lower():
                    score += 10
                # Brand match
                if query_lower in phone["brand"].lower():
                    score += 5
                # Highlights match
                for highlight in phone.get("highlights", []):
                    if query_lower in highlight.lower():
                        score += 3
                # Camera features match
                for feature in phone["camera"].get("features", []):
                    if query_lower in feature.lower():
                        score += 2
                # Processor match
                if query_lower in phone["processor"].lower():
                    score += 2

                if score > 0:
                    scored_results.append((phone, score))

            # Sort by score
            scored_results.sort(key=lambda x: x[1], reverse=True)
            results = [p for p, _ in scored_results]

        logger.info(f"Search returned {len(results[:limit])} phones")
        return results[:limit]

    def get_best_camera_phones(self, max_price: Optional[int] = None, limit: int = 5) -> list[dict]:
        """Get phones with the best cameras."""
        results = self.phones.copy()

        if max_price:
            results = [p for p in results if p["price"] <= max_price]

        # Score based on camera specs
        scored = []
        for phone in results:
            score = 0
            camera = phone["camera"]

            # Main camera megapixels
            main_mp = int(camera["main"].split()[0])
            score += main_mp / 10

            # Has telephoto
            if "telephoto" in camera:
                score += 20

            # Camera features
            features = camera.get("features", [])
            if "OIS" in features:
                score += 10
            if "Hasselblad" in features or "Leica" in features or "ZEISS" in features:
                score += 15
            if "8K Video" in features:
                score += 10
            if "ProRAW" in features or "ProRes" in features:
                score += 8

            # Rating
            score += phone.get("rating", 0) * 5

            scored.append((phone, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored[:limit]]

    def get_best_battery_phones(self, max_price: Optional[int] = None, limit: int = 5) -> list[dict]:
        """Get phones with the best battery life and charging."""
        results = self.phones.copy()

        if max_price:
            results = [p for p in results if p["price"] <= max_price]

        # Score based on battery
        scored = []
        for phone in results:
            score = 0
            battery = phone["battery"]

            # Battery capacity
            score += battery["capacity"] / 100

            # Fast charging
            charging = battery["charging"]
            if "120W" in charging or "125W" in charging:
                score += 30
            elif "100W" in charging:
                score += 25
            elif "80W" in charging or "90W" in charging:
                score += 20
            elif "65W" in charging or "67W" in charging:
                score += 15
            elif "45W" in charging:
                score += 10

            # Wireless charging
            if "wireless" in charging.lower():
                score += 5

            scored.append((phone, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored[:limit]]

    def get_compact_phones(self, min_price: Optional[int] = None, max_price: Optional[int] = None, min_ram: Optional[int] = None, limit: int = 5) -> list[dict]:
        """Get compact phones good for one-hand use."""
        results = self.phones.copy()

        if min_price:
            results = [p for p in results if p["price"] >= min_price]
        if max_price:
            results = [p for p in results if p["price"] <= max_price]
        if min_ram:
            results = [p for p in results if p["ram"] >= min_ram]

        # Filter phones with smaller displays
        results = [p for p in results if p["display"]["size"] <= 6.4]

        # Sort by display size (smaller first)
        results.sort(key=lambda x: x["display"]["size"])

        return results[:limit]

    def get_gaming_phones(self, max_price: Optional[int] = None, limit: int = 5) -> list[dict]:
        """Get phones best for gaming."""
        results = self.phones.copy()

        if max_price:
            results = [p for p in results if p["price"] <= max_price]

        # Score for gaming
        scored = []
        for phone in results:
            score = 0

            # High refresh rate
            refresh = phone["display"]["refresh_rate"]
            score += refresh / 10

            # Flagship processors
            processor = phone["processor"].lower()
            if "snapdragon 8 gen 3" in processor:
                score += 50
            elif "snapdragon 8 gen 2" in processor or "snapdragon 8s gen 3" in processor:
                score += 40
            elif "snapdragon 8+ gen 1" in processor:
                score += 35
            elif "dimensity 9" in processor:
                score += 35
            elif "a17 pro" in processor:
                score += 45

            # RAM
            score += phone["ram"] * 2

            # Battery
            score += phone["battery"]["capacity"] / 200

            # Gaming brands/highlights
            if phone["brand"] in ["ASUS", "iQOO"]:
                score += 10
            for highlight in phone.get("highlights", []):
                if "gaming" in highlight.lower():
                    score += 15

            scored.append((phone, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored[:limit]]

    def compare_phones(self, phone_ids: list[str]) -> list[dict]:
        """Compare multiple phones by their IDs."""
        phones = []
        for phone_id in phone_ids:
            # Try by ID first
            phone = self.get_phone_by_id(phone_id)
            if not phone:
                # Try by name
                phone = self.get_phone_by_name(phone_id)
            if phone:
                phones.append(phone)
        return phones

    def get_phones_by_brand(self, brand: str, max_price: Optional[int] = None, limit: int = 10) -> list[dict]:
        """Get all phones from a specific brand."""
        results = [p for p in self.phones if p["brand"].lower() == brand.lower()]

        if max_price:
            results = [p for p in results if p["price"] <= max_price]

        # Sort by price descending (flagship first)
        results.sort(key=lambda x: x["price"], reverse=True)

        return results[:limit]

    def get_available_brands(self) -> list[str]:
        """Get list of all available brands."""
        return self.brands

    def format_phone_summary(self, phone: dict) -> str:
        """Format phone details as a readable summary."""
        return f"""
**{phone['name']}** by {phone['brand']}
- **Price:** ₹{phone['price']:,}
- **Display:** {phone['display']['size']}" {phone['display']['type']} @ {phone['display']['refresh_rate']}Hz
- **Processor:** {phone['processor']}
- **RAM:** {phone['ram']}GB
- **Camera:** {phone['camera']['main']} main
- **Battery:** {phone['battery']['capacity']}mAh, {phone['battery']['charging']}
- **5G:** {'Yes' if phone['5g'] else 'No'}
- **Highlights:** {', '.join(phone.get('highlights', []))}
- **Rating:** {phone.get('rating', 'N/A')}/5
"""

    def format_comparison_table(self, phones: list[dict]) -> str:
        """Format a comparison of multiple phones as a table."""
        if not phones:
            return "No phones to compare."

        headers = ["Feature"] + [p["name"] for p in phones]
        rows = [
            ["Price"] + [f"₹{p['price']:,}" for p in phones],
            ["Display"] + [f"{p['display']['size']}\" {p['display']['refresh_rate']}Hz" for p in phones],
            ["Processor"] + [p["processor"] for p in phones],
            ["RAM"] + [f"{p['ram']}GB" for p in phones],
            ["Main Camera"] + [p["camera"]["main"] for p in phones],
            ["Battery"] + [f"{p['battery']['capacity']}mAh" for p in phones],
            ["Charging"] + [p["battery"]["charging"].split(",")[0] for p in phones],
            ["5G"] + ["Yes" if p["5g"] else "No" for p in phones],
            ["Water Resistance"] + [p.get("water_resistance", "None") for p in phones],
            ["Rating"] + [f"{p.get('rating', 'N/A')}/5" for p in phones],
        ]

        # Format as markdown table
        table = "| " + " | ".join(headers) + " |\n"
        table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            table += "| " + " | ".join(row) + " |\n"

        return table


# Singleton instance
phone_service = PhoneService()
