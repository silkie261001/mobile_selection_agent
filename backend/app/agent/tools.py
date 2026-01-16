"""
Tools for the shopping chat agent.
Simplified to 3 core tools - LLM decides how to use them.
"""
from langchain.tools import tool
from typing import Optional
from ..data.phone_service import phone_service


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
        use_case: The primary purpose for the phone. Options: "camera", "gaming", "battery", "compact"
        brand: Filter by brand name (e.g., "Samsung", "Apple", "OnePlus")
        min_price: Minimum price in rupees
        max_price: Maximum price in rupees
        min_ram: Minimum RAM in GB
        has_5g: Set true for 5G phones only
        min_battery: Minimum battery capacity in mAh
        limit: Maximum number of results (default 5)

    Returns:
        List of matching phones with specs
    """
    # Handle string values from LLM
    if min_price is not None:
        try:
            min_price = int(min_price) if min_price else None
        except (ValueError, TypeError):
            min_price = None
    if max_price is not None:
        try:
            max_price = int(max_price) if max_price else None
        except (ValueError, TypeError):
            max_price = None
    if min_ram is not None:
        try:
            min_ram = int(min_ram) if min_ram else None
        except (ValueError, TypeError):
            min_ram = None
    if min_battery is not None:
        try:
            min_battery = int(min_battery) if min_battery else None
        except (ValueError, TypeError):
            min_battery = None
    if limit is not None:
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 5

    # Handle use_case parameter
    use_case_lower = use_case.lower().strip() if use_case else None

    # Route to appropriate search based on use_case
    if use_case_lower in ["camera", "photography", "photo", "photos"]:
        phones = phone_service.get_best_camera_phones(max_price=max_price, limit=limit)
        category = "Best Camera Phones"
    elif use_case_lower in ["gaming", "game", "games"]:
        phones = phone_service.get_gaming_phones(max_price=max_price, limit=limit)
        category = "Best Gaming Phones"
    elif use_case_lower in ["battery", "battery life", "long battery"]:
        phones = phone_service.get_best_battery_phones(max_price=max_price, limit=limit)
        category = "Best Battery Phones"
    elif use_case_lower in ["compact", "small", "one-hand", "one hand"]:
        phones = phone_service.get_compact_phones(min_price=min_price, max_price=max_price, min_ram=min_ram, limit=limit)
        category = "Compact Phones"
    elif brand:
        phones = phone_service.get_phones_by_brand(brand, max_price=max_price, limit=limit)
        category = f"{brand} Phones"
    else:
        # General search
        phones = phone_service.search_phones(
            brand=brand,
            min_price=min_price,
            max_price=max_price,
            min_ram=min_ram,
            has_5g=has_5g,
            min_battery=min_battery,
            limit=limit
        )
        category = "Phones"

    if not phones:
        return "No phones found matching your criteria. Try adjusting your filters."

    # Build output
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
        phone_name: The name of the phone (e.g., "iPhone 15 Pro", "Samsung Galaxy S24 Ultra", "OnePlus 12")

    Returns:
        Complete specifications and details of the phone
    """
    # Try by ID first, then by name
    phone = phone_service.get_phone_by_id(phone_name)
    if not phone:
        phone = phone_service.get_phone_by_name(phone_name)

    if not phone:
        # Try to suggest similar phones
        available = phone_service.get_available_brands()
        return f"Phone '{phone_name}' not found. Available brands: {', '.join(available)}. Try searching with a different name."

    camera = phone['camera']
    camera_specs = f"Main: {camera['main']}"
    if 'ultrawide' in camera:
        camera_specs += f" | Ultrawide: {camera['ultrawide']}"
    if 'telephoto' in camera:
        camera_specs += f" | Telephoto: {camera['telephoto']}"
    camera_specs += f" | Front: {camera['front']}"

    output = f"""# {phone['name']}

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
    return output


@tool
def compare_phones(phone_names: str) -> str:
    """
    Compare 2-4 phones side by side with a detailed comparison table.

    Args:
        phone_names: Comma-separated list of phone names to compare
                    (e.g., "iPhone 15, Samsung S24, OnePlus 12")

    Returns:
        Comparison table with all specifications and analysis
    """
    names = [n.strip() for n in phone_names.split(",")]

    if len(names) < 2:
        return "Please provide at least 2 phone names separated by commas to compare."
    if len(names) > 4:
        return "Please compare a maximum of 4 phones at a time for readability."

    phones = phone_service.compare_phones(names)

    if len(phones) < 2:
        found = [p['name'] for p in phones] if phones else []
        available = phone_service.get_available_brands()
        return f"Could only find {len(phones)} phone(s): {found}. Available brands: {', '.join(available)}. Please check the names and try again."

    # Create comparison table
    table = phone_service.format_comparison_table(phones)

    # Add analysis
    analysis = "\n## Analysis\n\n"

    # Price comparison
    prices = [(p['name'], p['price']) for p in phones]
    prices.sort(key=lambda x: x[1])
    analysis += f"**Best Value:** {prices[0][0]} is the most affordable at ₹{prices[0][1]:,}\n\n"

    # Camera comparison
    best_camera = max(phones, key=lambda p: int(p['camera']['main'].split()[0]))
    analysis += f"**Best Camera (by MP):** {best_camera['name']} with {best_camera['camera']['main']}\n\n"

    # Battery comparison
    best_battery = max(phones, key=lambda p: p['battery']['capacity'])
    analysis += f"**Best Battery:** {best_battery['name']} with {best_battery['battery']['capacity']}mAh\n\n"

    # Performance comparison
    flagships = ["snapdragon 8 gen 3", "a17 pro", "a18 pro", "dimensity 9300", "dimensity 9400"]
    for p in phones:
        if any(f in p['processor'].lower() for f in flagships):
            analysis += f"**Best Performance:** {p['name']} with {p['processor']}\n\n"
            break

    return table + analysis


# Export all tools
def get_all_tools():
    """Get all available tools for the agent."""
    return [
        search_phones,
        get_phone_details,
        compare_phones,
    ]
