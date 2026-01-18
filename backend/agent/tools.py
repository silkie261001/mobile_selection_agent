"""
Tools for the shopping chat agent.
LLM decides how to use these tools based on user queries.
"""
from langchain.tools import tool
from typing import Optional
from data.phone_service import phone_service


def _safe_int(value) -> Optional[int]:
    """Safely convert to int."""
    try:
        return int(value) if value else None
    except (ValueError, TypeError):
        return None


@tool
def search_phones(
    use_case: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_ram: Optional[int] = None,
    has_5g: Optional[bool] = None,
    min_battery: Optional[int] = None,
    limit: int = 5
) -> str:
    """
    Search and find phones based on various criteria.

    Args:
        use_case: Primary purpose (camera, gaming, battery, compact, etc.)
        brand: Filter by brand name
        min_price: Minimum price in rupees
        max_price: Maximum price in rupees
        min_ram: Minimum RAM in GB
        has_5g: Set true for 5G phones only
        min_battery: Minimum battery capacity in mAh
        limit: Maximum number of results (default 5)

    Returns:
        List of matching phones with specs
    """
    min_price = _safe_int(min_price)
    max_price = _safe_int(max_price)
    min_ram = _safe_int(min_ram)
    min_battery = _safe_int(min_battery)
    limit = _safe_int(limit) or 5

    use_case_lower = (use_case or "").lower().strip()

    # Route to appropriate service method
    if use_case_lower and any(term in use_case_lower for term in ["camera", "photo", "photography"]):
        phones = phone_service.get_best_camera_phones(max_price=max_price, limit=limit)
        category = "Camera Phones"
    elif use_case_lower and any(term in use_case_lower for term in ["gaming", "game", "performance"]):
        phones = phone_service.get_gaming_phones(max_price=max_price, limit=limit)
        category = "Gaming Phones"
    elif use_case_lower and any(term in use_case_lower for term in ["battery", "long lasting", "endurance"]):
        phones = phone_service.get_best_battery_phones(max_price=max_price, limit=limit)
        category = "Battery Phones"
    elif use_case_lower and any(term in use_case_lower for term in ["compact", "small", "one hand", "mini"]):
        phones = phone_service.get_compact_phones(min_price=min_price, max_price=max_price, min_ram=min_ram, limit=limit)
        category = "Compact Phones"
    elif brand:
        phones = phone_service.get_phones_by_brand(brand, max_price=max_price, limit=limit)
        category = f"{brand} Phones"
    else:
        phones = phone_service.search_phones(
            brand=brand, min_price=min_price, max_price=max_price,
            min_ram=min_ram, has_5g=has_5g, min_battery=min_battery, limit=limit
        )
        category = "Phones"

    if not phones:
        return "No phones found matching your criteria."

    budget_text = f" under ₹{max_price:,}" if max_price else ""
    output = f"# {category}{budget_text}\n\nFound {len(phones)} phones:\n\n"

    for i, phone in enumerate(phones, 1):
        output += f"## {i}. {phone['name']} - ₹{phone['price']:,}\n"
        output += f"- **Display:** {phone['display']['size']}\" {phone['display']['type']} @ {phone['display']['refresh_rate']}Hz\n"
        output += f"- **Processor:** {phone['processor']} | {phone['ram']}GB RAM\n"
        output += f"- **Camera:** {phone['camera']['main']}\n"
        output += f"- **Battery:** {phone['battery']['capacity']}mAh | {phone['battery']['charging'].split(',')[0]}\n"
        output += f"- **5G:** {'Yes' if phone['5g'] else 'No'}\n"
        output += f"- **Rating:** {phone.get('rating', 'N/A')}/5\n"
        if phone.get('highlights'):
            output += f"- **Highlights:** {', '.join(phone.get('highlights', []))}\n"
        output += "\n"

    return output


@tool
def get_phone_details(phone_name: str) -> str:
    """
    Get comprehensive details about a specific phone.

    Args:
        phone_name: The name of the phone to look up

    Returns:
        Complete specifications and details of the phone
    """
    phone = phone_service.get_phone_by_id(phone_name) or phone_service.get_phone_by_name(phone_name)

    if not phone:
        available = phone_service.get_available_brands()
        return f"Phone '{phone_name}' not found. Available brands: {', '.join(available)}."

    camera = phone['camera']
    camera_specs = f"Main: {camera['main']}"
    if 'ultrawide' in camera:
        camera_specs += f" | Ultrawide: {camera['ultrawide']}"
    if 'telephoto' in camera:
        camera_specs += f" | Telephoto: {camera['telephoto']}"
    camera_specs += f" | Front: {camera['front']}"

    return f"""# {phone['name']}

## Basic Info
- **Brand:** {phone['brand']}
- **Price:** ₹{phone['price']:,}
- **Release Date:** {phone.get('release_date', 'N/A')}
- **Rating:** {phone.get('rating', 'N/A')}/5
- **Colors:** {', '.join(phone.get('colors', []))}

## Display
- **Size:** {phone['display']['size']} inches
- **Type:** {phone['display']['type']}
- **Resolution:** {phone['display']['resolution']}
- **Refresh Rate:** {phone['display']['refresh_rate']}Hz

## Performance
- **Processor:** {phone['processor']}
- **RAM:** {phone['ram']}GB
- **Storage Options:** {', '.join(str(s) + 'GB' for s in phone['storage'])}

## Camera
- **Setup:** {camera_specs}
- **Features:** {', '.join(camera.get('features', []))}

## Battery
- **Capacity:** {phone['battery']['capacity']}mAh
- **Charging:** {phone['battery']['charging']}

## Connectivity & Features
- **5G:** {'Yes' if phone['5g'] else 'No'}
- **NFC:** {'Yes' if phone.get('nfc') else 'No'}
- **Water Resistance:** {phone.get('water_resistance', 'None')}
- **Weight:** {phone.get('weight', 'N/A')}g

## Highlights
{chr(10).join('- ' + h for h in phone.get('highlights', []))}
"""


@tool
def compare_phones(phone_names: str) -> str:
    """
    Compare 2-4 phones side by side with a detailed comparison table.

    Args:
        phone_names: Comma-separated list of phone names to compare

    Returns:
        Comparison table with specifications for LLM to analyze
    """
    names = [n.strip() for n in phone_names.split(",")]

    if len(names) < 2:
        return "Please provide at least 2 phone names separated by commas."
    if len(names) > 4:
        return "Please compare a maximum of 4 phones."

    phones = phone_service.compare_phones(names)

    if len(phones) < 2:
        found = [p['name'] for p in phones] if phones else []
        available = phone_service.get_available_brands()
        return f"Found only {len(phones)} phone(s): {found}. Available brands: {', '.join(available)}."

    table = phone_service.format_comparison_table(phones)
    return f"{table}\n\nAnalyze the comparison above and provide insights based only on this data."


@tool
def explain_mobile_tech(query: str) -> str:
    """
    Explain mobile phone technology terms and concepts.
    Use only for mobile phone related technical terms.
    Do not use for non-mobile topics.

    Args:
        query: The technical question about mobile phones

    Returns:
        Query with structure guidelines for LLM to explain
    """
    return f"""Explain this mobile phone technology: {query}

Provide a clear, educational explanation following this structure:
1. **Full Form**: If it's an acronym, state what it stands for
2. **What It Is**: Explain in simple, non-technical language
3. **How It Works**: Brief explanation (1-2 sentences)
4. **Why It Matters**: How it affects user experience on a phone
5. **Comparison** (if applicable): If user asked "X vs Y", explain key differences
6. **Verdict**: Practical recommendation for typical phone users

Keep explanation focused on mobile phones only. Use bullet points for clarity."""


def get_all_tools():
    """Get all available tools."""
    return [search_phones, get_phone_details, compare_phones, explain_mobile_tech]
