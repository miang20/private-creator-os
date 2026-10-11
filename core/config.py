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

def openai_api_key() -> Optional[str]:
    return get_secret("OPENAI_API_KEY")

def youtube_api_key() -> Optional[str]:
    return get_secret("YOUTUBE_API_KEY")
