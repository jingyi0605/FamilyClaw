from __future__ import annotations

from pathlib import Path
from typing import Any


THEME_REGISTRY_SOURCE_PATH = Path(__file__).resolve()
THEME_PLUGIN_VERSION = "1.0.0"
THEME_STORAGE_KEY = "familyclaw-theme"
DEFAULT_THEME_ID = "chun-he-jing-ming"

_THEME_ITEMS: list[dict[str, Any]] = [
    {
        "theme_id": "chun-he-jing-ming",
        "display_name": "春和景明",
        "description": "温暖宁静，适合日常使用",
        "accent_color": "#d97756",
        "preview_surface": "#f7f5f2",
        "emoji": "🌸",
    },
    {
        "theme_id": "yue-lang-xing-xi",
        "display_name": "月朗星稀",
        "description": "柔和深色，减少视觉疲劳",
        "accent_color": "#7c8cff",
        "preview_surface": "#0f1117",
        "emoji": "🌙",
    },
    {
        "theme_id": "ming-cha-qiu-hao",
        "display_name": "明察秋毫",
        "description": "更大字号、更高对比度",
        "accent_color": "#b7791f",
        "preview_surface": "#f5f5f0",
        "emoji": "🔍",
    },
    {
        "theme_id": "wan-zi-qian-hong",
        "display_name": "万紫千红",
        "description": "鲜艳活泼，色彩绚烂",
        "accent_color": "#e879f9",
        "preview_surface": "#fef8ff",
        "emoji": "🌈",
    },
    {
        "theme_id": "feng-chi-dian-che",
        "display_name": "风驰电掣",
        "description": "霓虹电网，赛博激光",
        "accent_color": "#22d3ee",
        "preview_surface": "#160a22",
        "emoji": "⚡",
    },
    {
        "theme_id": "xing-he-wan-li",
        "display_name": "星河万里",
        "description": "星云流动，宇宙漫游",
        "accent_color": "#60a5fa",
        "preview_surface": "#0f1228",
        "emoji": "🚀",
    },
    {
        "theme_id": "qing-shan-lv-shui",
        "display_name": "青山绿水",
        "description": "自然清新，森林氧吧",
        "accent_color": "#34d399",
        "preview_surface": "#f2f7f3",
        "emoji": "🌿",
    },
    {
        "theme_id": "jin-xiu-qian-cheng",
        "display_name": "锦绣前程",
        "description": "鎏金尊贵，大气庄重",
        "accent_color": "#d4af37",
        "preview_surface": "#0e0c08",
        "emoji": "👑",
    },
]


def list_theme_catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for theme in _THEME_ITEMS:
        fallback_theme_id = None if theme["theme_id"] == DEFAULT_THEME_ID else DEFAULT_THEME_ID
        items.append(
            {
                "plugin_id": f"builtin.theme.{theme['theme_id']}",
                "plugin_name": theme["display_name"],
                "plugin_version": THEME_PLUGIN_VERSION,
                "compatibility": {
                    "theme_schema_version": 1,
                    "selection_storage_key": THEME_STORAGE_KEY,
                },
                "theme_id": theme["theme_id"],
                "display_name": theme["display_name"],
                "description": theme["description"],
                "tokens_resource": f"user-app://themes/{theme['theme_id']}",
                "preview": {
                    "accent_color": theme["accent_color"],
                    "preview_surface": theme["preview_surface"],
                    "emoji": theme["emoji"],
                },
                "fallback_theme_id": fallback_theme_id,
            }
        )
    return items
