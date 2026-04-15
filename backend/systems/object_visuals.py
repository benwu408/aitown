"""Pixel-spec generation and archetype reuse for world objects."""

import hashlib
import logging
import re

logger = logging.getLogger("agentica.object_visuals")

CATEGORY_BASES = {
    "tool": "tool",
    "structure": "structure",
    "container": "container",
    "food": "food",
    "medicine": "medicine",
    "art": "art",
    "clothing": "clothing",
    "document": "document",
    "marker": "marker",
    "furniture": "furniture",
    "mechanism": "mechanism",
    "other": "object",
}


def normalize_object_archetype(name: str, category: str, description: str = "") -> str:
    name_tokens = re.findall(r"[a-z]+", name.lower())
    desc_tokens = re.findall(r"[a-z]+", description.lower())
    tokens = name_tokens + desc_tokens
    stop = {
        "a", "an", "the", "very", "small", "large", "rough", "crude", "simple",
        "new", "old", "my", "their", "this", "that",
    }
    filtered = [token for token in tokens if token not in stop]
    material = next((t for t in filtered if t in {
        "wooden", "wood", "stone", "clay", "woven", "rope", "iron", "metal",
        "bone", "leather", "paper", "herbal", "reed", "fiber",
    }), "")
    material_aliases = {
        "wooden": "wood",
        "metal": "iron",
        "woven": "fiber",
    }
    material = material_aliases.get(material, material)
    noun = next((t for t in reversed(name_tokens) if t not in stop and t != material), "")
    if not noun:
        noun = next((t for t in reversed(filtered) if t not in {material}), "") or CATEGORY_BASES.get(category, "object")
    bits = [material, noun] if material else [noun]
    normalized = "_".join(bit for bit in bits if bit)
    return normalized or CATEGORY_BASES.get(category, "object")


def _validate_pixel_spec(spec: dict) -> bool:
    if not isinstance(spec, dict):
        return False
    size = int(spec.get("size", 0) or 0)
    pixels = spec.get("pixels")
    palette = spec.get("palette")
    if size not in (16, 24):
        return False
    if not isinstance(palette, list) or not palette:
        return False
    if not isinstance(pixels, list) or len(pixels) != size:
        return False
    return all(isinstance(row, str) and len(row) == size for row in pixels)


def _fallback_pixel_spec(archetype: str, category: str) -> dict:
    digest = hashlib.md5(f"{archetype}:{category}".encode("utf-8")).hexdigest()
    size = 16
    palette = ["transparent", "#2d2016", "#7c5a35", "#c7ab72", "#e9dcb0"]
    if category == "food":
        palette = ["transparent", "#2f5d2f", "#6f9c3b", "#c99b44", "#f3ddb1"]
    elif category == "medicine":
        palette = ["transparent", "#1e3c2a", "#4d8c57", "#b9d97c", "#f2efd7"]
    elif category == "clothing":
        palette = ["transparent", "#3f315e", "#6d5a9d", "#b0a0d6", "#eee7ff"]
    elif category == "document":
        palette = ["transparent", "#5e4f37", "#b28e5f", "#ede1b4", "#fff7e0"]

    pixels = []
    for row in range(size):
        chars = []
        for col in range(size):
            edge = row in (0, size - 1) or col in (0, size - 1)
            center = 4 <= row <= 11 and 4 <= col <= 11
            bit = int(digest[(row + col) % len(digest)], 16)
            if edge and bit % 5 == 0:
                chars.append("0")
            elif center and ((row - 7) ** 2 + (col - 7) ** 2) < 18:
                chars.append(str(1 + bit % (len(palette) - 1)))
            elif 3 <= row <= 12 and 3 <= col <= 12 and bit % 7 < 2:
                chars.append(str(1 + bit % (len(palette) - 1)))
            else:
                chars.append("0")
        pixels.append("".join(chars))
    return {
        "size": size,
        "palette": palette,
        "pixels": pixels,
        "anchor": {"x": 0.5, "y": 0.7},
        "hand_offset": {"x": 5, "y": -8},
        "rotation_hint": -0.15 if category in {"tool", "weapon", "mechanism"} else 0.0,
    }


async def ensure_object_visual(world, obj) -> dict:
    from llm.client import llm_client

    archetype = obj.visual_archetype or normalize_object_archetype(obj.name, obj.category, obj.description)
    obj.visual_archetype = archetype

    cached = getattr(world, "object_visual_registry", {}).get(archetype)
    if cached:
        obj.pixel_spec = cached
        return cached

    prompt = f"""Create a tiny pixel-art sprite spec for a frontier-settlement object.
Object archetype: {archetype}
Object name: {obj.name}
Category: {obj.category}
Description: {obj.description or obj.visual_description or "simple handmade object"}

Return JSON only:
{{
  "size": 16 or 24,
  "palette": ["transparent", "#hex", "#hex", "#hex", "#hex"],
  "pixels": ["rowstring", "... exactly size rows, each exactly size chars using digits indexing palette"],
  "anchor": {{"x": 0.0-1.0, "y": 0.0-1.0}},
  "hand_offset": {{"x": integer, "y": integer}},
  "rotation_hint": -1.0 to 1.0
}}

Make it readable at tiny scale, earthy, handmade, and suitable for isometric frontier visuals."""

    generated = await llm_client.generate_json(
        "You design tiny pixel-art object specs for a game. Return valid JSON only.",
        prompt,
        default={},
        temperature=0.4,
        max_tokens=500,
    )
    spec = generated if _validate_pixel_spec(generated) else _fallback_pixel_spec(archetype, obj.category)
    world.object_visual_registry[archetype] = spec
    obj.pixel_spec = spec
    return spec
