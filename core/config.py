from __future__ import annotations
import os
from typing import Optional


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return default


def youtube_api_key() -> Optional[str]:
    """Optional key for official YouTube Data API search (free quota applies)."""
    return get_secret("YOUTUBE_API_KEY")
