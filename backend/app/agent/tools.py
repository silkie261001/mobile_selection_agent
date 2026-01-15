"""
Tools for the shopping chat agent.
"""
from langchain.tools import tool
from typing import Optional
from ..data.phone_service import phone_service


@tool
def search_phones(
    query: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_ram: Optional[int] = None,
    has_5g: Optional[bool] = None,
    min_battery: Optional[int] = None,
    limit: int = 5
) -> str:
    """
    General phone search with filters. Use this for budget-based searches or brand searches.
    For specific use cases, prefer specialized tools: get_best_camera_phones, get_best_battery_phones, get_gaming_phones.

    Args:
        query: Optional text to match phone names (leave empty for general search)
        brand: Filter by brand name (e.g., "Samsung", "Apple", "OnePlus")
        min_price: Minimum price in rupees (use 0 or leave empty for no minimum)
        max_price: Maximum price in rupees (e.g., 30000, 50000)
        min_ram: Minimum RAM in GB
        has_5g: Set true for 5G phones only
        min_battery: Minimum battery capacity in mAh
        limit: Maximum number of results (default 5)

    Returns:
        List of matching phones with specs
    """
    # Handle string values from LLM
    if min_price is not None:
        min_price = int(min_price) if min_price else None
    if max_price is not None:
        max_price = int(max_price) if max_price else None
    if min_ram is not None:
        min_ram = int(min_ram) if min_ram else None
    if min_battery is not None:
        min_battery = int(min_battery) if min_battery else None
    if limit is not None:
        limit = int(limit)

    results = phone_service.search_phones(
        query=query,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_ram=min_ram,
        has_5g=has_5g,
        min_battery=min_battery,
        limit=limit
    )

    if not results:
        return "No phones found matching your criteria. Try adjusting your filters."

    output = f"Found {len(results)} phones:\n\n"
    for phone in results:
        output += f"**{phone['name']}** - ₹{phone['price']:,}\n"
        output += f"  • {phone['display']['size']}\" {phone['display']['type']} @ {phone['display']['refresh_rate']}Hz\n"
        output += f"  • {phone['processor']} | {phone['ram']}GB RAM\n"
        output += f"  • Camera: {phone['camera']['main']}\n"
        output += f"  • Battery: {phone['battery']['capacity']}mAh | {phone['battery']['charging'].split(',')[0]}\n"
        output += f"  • Rating: {phone.get('rating', 'N/A')}/5\n"
        output += f"  • Highlights: {', '.join(phone.get('highlights', []))}\n\n"

    return output


@tool
def get_phone_details(phone_name: str) -> str:
    """
    Get detailed information about a specific phone.

    Args:
        phone_name: The name or ID of the phone (e.g., "iPhone 15 Pro", "samsung-s24-ultra")

    Returns:
        Comprehensive details about the phone
    """
    # Try by ID first
    phone = phone_service.get_phone_by_id(phone_name)
    if not phone:
        # Try by name
        phone = phone_service.get_phone_by_name(phone_name)

    if not phone:
        return f"Phone '{phone_name}' not found in the database. Please check the name and try again."

    camera = phone['camera']
    camera_specs = f"Main: {camera['main']}"
    if 'ultrawide' in camera:
        camera_specs += f" | Ultrawide: {camera['ultrawide']}"
    if 'telephoto' in camera:
        camera_specs += f" | Telephoto: {camera['telephoto']}"
    camera_specs += f" | Front: {camera['front']}"

    output = f"""
# {phone['name']}

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
    Compare 2-3 phones side by side.

    Args:
        phone_names: Comma-separated list of phone names to compare
                    (e.g., "Pixel 8a, OnePlus 12R, Samsung S24")

    Returns:
        Comparison table and analysis of the phones
    """
    names = [n.strip() for n in phone_names.split(",")]

    if len(names) < 2:
        return "Please provide at least 2 phone names separated by commas."
    if len(names) > 4:
        return "Please compare a maximum of 4 phones at a time."

    phones = phone_service.compare_phones(names)

    if len(phones) < 2:
        found = [p['name'] for p in phones] if phones else []
        return f"Could only find {len(phones)} phone(s): {found}. Please check the names and try again."

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
    flagships = ["snapdragon 8 gen 3", "a17 pro", "dimensity 9300"]
    for p in phones:
        if any(f in p['processor'].lower() for f in flagships):
            analysis += f"**Best Performance:** {p['name']} with {p['processor']}\n\n"
            break

    return table + analysis


@tool
def get_best_camera_phones(max_price: Optional[int] = None, limit: int = 5) -> str:
    """
    ALWAYS use this tool when user asks for best camera phones, camera recommendations, or photography phones.
    Returns phones ranked by camera quality including megapixels, OIS, telephoto, and features.

    Args:
        max_price: Maximum price in rupees (e.g., 30000, 50000). Leave empty for no limit.
        limit: Number of phones to return (default 5)

    Returns:
        List of best camera phones with camera specs and features
    """
    # Handle string values from LLM
    if max_price is not None:
        max_price = int(max_price)
    if limit is not None:
        limit = int(limit)
    phones = phone_service.get_best_camera_phones(max_price=max_price, limit=limit)

    if not phones:
        return "No camera phones found within your budget."

    budget_text = f" under ₹{max_price:,}" if max_price else ""
    output = f"# Best Camera Phones{budget_text}\n\n"

    for i, phone in enumerate(phones, 1):
        camera = phone['camera']
        features = ', '.join(camera.get('features', []))
        output += f"## {i}. {phone['name']} - ₹{phone['price']:,}\n"
        output += f"- **Main Camera:** {camera['main']}\n"
        if 'telephoto' in camera:
            output += f"- **Telephoto:** {camera['telephoto']}\n"
        output += f"- **Camera Features:** {features}\n"
        output += f"- **Why it's great:** {', '.join(phone.get('highlights', []))}\n\n"

    return output


@tool
def get_best_battery_phones(max_price: Optional[int] = None, limit: int = 5) -> str:
    """
    Get phones with the best battery life and charging.

    Args:
        max_price: Maximum price in rupees (optional)
        limit: Number of phones to return (default 5)

    Returns:
        List of best battery phones
    """
    phones = phone_service.get_best_battery_phones(max_price=max_price, limit=limit)

    if not phones:
        return "No phones found within your budget."

    budget_text = f" under ₹{max_price:,}" if max_price else ""
    output = f"# Best Battery Phones{budget_text}\n\n"

    for i, phone in enumerate(phones, 1):
        battery = phone['battery']
        output += f"## {i}. {phone['name']} - ₹{phone['price']:,}\n"
        output += f"- **Battery:** {battery['capacity']}mAh\n"
        output += f"- **Charging:** {battery['charging']}\n"
        output += f"- **Highlights:** {', '.join(phone.get('highlights', []))}\n\n"

    return output


@tool
def get_compact_phones(max_price: Optional[int] = None, limit: int = 5) -> str:
    """
    Get compact phones suitable for one-hand use.

    Args:
        max_price: Maximum price in rupees (optional)
        limit: Number of phones to return (default 5)

    Returns:
        List of compact phones
    """
    phones = phone_service.get_compact_phones(max_price=max_price, limit=limit)

    if not phones:
        return "No compact phones found. Most modern phones are 6.5\" or larger."

    output = "# Compact Phones (Good for One-Hand Use)\n\n"

    for i, phone in enumerate(phones, 1):
        output += f"## {i}. {phone['name']} - ₹{phone['price']:,}\n"
        output += f"- **Display:** {phone['display']['size']}\" {phone['display']['type']}\n"
        output += f"- **Weight:** {phone.get('weight', 'N/A')}g\n"
        output += f"- **Highlights:** {', '.join(phone.get('highlights', []))}\n\n"

    return output


@tool
def get_gaming_phones(max_price: Optional[int] = None, limit: int = 5) -> str:
    """
    Get the best phones for gaming.

    Args:
        max_price: Maximum price in rupees (optional)
        limit: Number of phones to return (default 5)

    Returns:
        List of best gaming phones
    """
    phones = phone_service.get_gaming_phones(max_price=max_price, limit=limit)

    if not phones:
        return "No gaming phones found within your budget."

    budget_text = f" under ₹{max_price:,}" if max_price else ""
    output = f"# Best Gaming Phones{budget_text}\n\n"

    for i, phone in enumerate(phones, 1):
        output += f"## {i}. {phone['name']} - ₹{phone['price']:,}\n"
        output += f"- **Processor:** {phone['processor']}\n"
        output += f"- **RAM:** {phone['ram']}GB\n"
        output += f"- **Display:** {phone['display']['size']}\" @ {phone['display']['refresh_rate']}Hz\n"
        output += f"- **Battery:** {phone['battery']['capacity']}mAh | {phone['battery']['charging'].split(',')[0]}\n"
        output += f"- **Highlights:** {', '.join(phone.get('highlights', []))}\n\n"

    return output


@tool
def get_phones_by_brand(brand: str, max_price: Optional[int] = None, limit: int = 10) -> str:
    """
    Get all phones from a specific brand.

    Args:
        brand: The brand name (e.g., "Samsung", "Apple", "OnePlus")
        max_price: Maximum price in rupees (optional)
        limit: Maximum number of results (default 10)

    Returns:
        List of phones from that brand
    """
    phones = phone_service.get_phones_by_brand(brand, max_price=max_price, limit=limit)

    if not phones:
        available = phone_service.get_available_brands()
        return f"No phones found for brand '{brand}'. Available brands: {', '.join(available)}"

    budget_text = f" under ₹{max_price:,}" if max_price else ""
    output = f"# {brand} Phones{budget_text}\n\n"

    for phone in phones:
        output += f"**{phone['name']}** - ₹{phone['price']:,}\n"
        output += f"  • {phone['processor']} | {phone['ram']}GB RAM\n"
        output += f"  • {phone['display']['size']}\" {phone['display']['refresh_rate']}Hz\n"
        output += f"  • Rating: {phone.get('rating', 'N/A')}/5\n\n"

    return output


@tool
def get_available_brands() -> str:
    """
    Get a list of all available phone brands in the database.

    Returns:
        List of brand names
    """
    brands = phone_service.get_available_brands()
    return f"Available brands: {', '.join(brands)}"


# Export all tools
def get_all_tools():
    """Get all available tools for the agent."""
    return [
        search_phones,
        get_phone_details,
        compare_phones,
        get_best_camera_phones,
        get_best_battery_phones,
        get_compact_phones,
        get_gaming_phones,
        get_phones_by_brand,
        get_available_brands,
    ]
