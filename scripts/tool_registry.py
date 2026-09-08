"""Canonical Forge Files user-facing feature registry.

The JSON file beside this module is intentionally the source of truth: Python
tests and the Node-based Capacitor builder both consume the same data, so a
mobile parity assertion cannot drift into a second hand-maintained catalogue.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


REGISTRY_PATH = Path(__file__).with_suffix(".json")

_REQUIRED_TOOL_FIELDS = {
    "id",
    "label",
    "category",
    "surface_kind",
    "web_card",
    "mobile",
    "mobile_mode",
    "mobile_surface",
    "processing",
    "api_paths",
    "output",
    "auth",
    "premium",
    "seo_slugs",
}
_MOBILE_MODES = {"shared", "native", "server"}
_PROCESSING_MODES = {"local", "local_or_server", "server"}


def load_registry(path: Path = REGISTRY_PATH) -> Dict[str, Any]:
    """Load and validate the language-neutral registry document."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("tool registry schema_version must be 1")

    tools = data.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("tool registry must contain a non-empty tools list")

    ids: set[str] = set()
    cards: set[str] = set()
    slugs: set[str] = set()
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            raise ValueError(f"tool at index {index} must be an object")
        missing = _REQUIRED_TOOL_FIELDS - tool.keys()
        if missing:
            raise ValueError(
                f"tool at index {index} is missing fields: {sorted(missing)}"
            )

        tool_id = tool["id"]
        if not isinstance(tool_id, str) or not tool_id:
            raise ValueError(f"tool at index {index} has an invalid id")
        if tool_id in ids:
            raise ValueError(f"duplicate tool id: {tool_id}")
        ids.add(tool_id)

        if tool["mobile_mode"] not in _MOBILE_MODES:
            raise ValueError(f"{tool_id} has invalid mobile_mode")
        if tool["processing"] not in _PROCESSING_MODES:
            raise ValueError(f"{tool_id} has invalid processing mode")
        if not isinstance(tool["mobile"], bool):
            raise ValueError(f"{tool_id} mobile must be boolean")
        if not isinstance(tool["auth"], bool) or not isinstance(tool["premium"], bool):
            raise ValueError(f"{tool_id} auth/premium must be boolean")
        if not isinstance(tool["api_paths"], list) or not tool["api_paths"]:
            raise ValueError(f"{tool_id} must declare at least one API path")
        if not all(isinstance(path, str) and path.startswith("/") for path in tool["api_paths"]):
            raise ValueError(f"{tool_id} contains an invalid API path")

        web_card = tool["web_card"]
        if web_card is not None:
            if not isinstance(web_card, str) or not web_card:
                raise ValueError(f"{tool_id} has an invalid web_card")
            if web_card in cards:
                raise ValueError(f"duplicate web_card: {web_card}")
            cards.add(web_card)

        if tool["mobile"] and not tool["mobile_surface"]:
            raise ValueError(f"mobile tool {tool_id} has no mobile_surface")
        if tool["mobile_mode"] == "shared" and tool["mobile_surface"] != web_card:
            raise ValueError(
                f"shared tool {tool_id} must use its web_card as mobile_surface"
            )

        seo_slugs = tool["seo_slugs"]
        if not isinstance(seo_slugs, list):
            raise ValueError(f"{tool_id} seo_slugs must be a list")
        for slug in seo_slugs:
            if not isinstance(slug, str) or not slug:
                raise ValueError(f"{tool_id} contains an invalid SEO slug")
            if slug in slugs:
                raise ValueError(f"duplicate SEO slug: {slug}")
            slugs.add(slug)

    for key in ("mobile_exemptions", "support_api_routes"):
        rows = data.get(key)
        if not isinstance(rows, list):
            raise ValueError(f"tool registry {key} must be a list")
        for row in rows:
            if not isinstance(row, dict) or not str(row.get("reason", "")).strip():
                raise ValueError(f"every {key} entry needs an explicit reason")

    return data


REGISTRY = load_registry()
TOOL_REGISTRY: List[Dict[str, Any]] = REGISTRY["tools"]
MOBILE_EXEMPTIONS: List[Dict[str, str]] = REGISTRY["mobile_exemptions"]
SUPPORT_API_ROUTES: List[Dict[str, str]] = REGISTRY["support_api_routes"]

TOOLS_BY_ID = {tool["id"]: tool for tool in TOOL_REGISTRY}
TOOLS_BY_SEO_SLUG = {
    slug: tool for tool in TOOL_REGISTRY for slug in tool["seo_slugs"]
}

