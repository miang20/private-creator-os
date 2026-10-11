from __future__ import annotations
from typing import Any
import requests
from .config import youtube_api_key

BASE = "https://www.googleapis.com/youtube/v3"

def search_youtube(query: str, max_results: int = 10) -> dict[str, Any]:
    key = youtube_api_key()
    if not key:
        return {"configured": False, "message": "Add YOUTUBE_API_KEY in Streamlit Secrets to query live YouTube data. No live results are fabricated.", "items": []}
    try:
        response = requests.get(f"{BASE}/search", params={"part":"snippet","q":query,"type":"video","order":"viewCount","maxResults":max(1,min(max_results,25)),"key":key}, timeout=20)
        response.raise_for_status()
        raw = response.json().get("items", [])
        ids = [x.get("id", {}).get("videoId") for x in raw if x.get("id", {}).get("videoId")]
        stats = {}
        if ids:
            s = requests.get(f"{BASE}/videos", params={"part":"statistics,contentDetails","id":",".join(ids),"key":key}, timeout=20)
            s.raise_for_status()
            stats = {x["id"]: x for x in s.json().get("items", [])}
        items = []
        for x in raw:
            vid = x.get("id", {}).get("videoId")
            snippet = x.get("snippet", {})
            item_stats = stats.get(vid, {}).get("statistics", {})
            items.append({"title":snippet.get("title",""),"channel":snippet.get("channelTitle",""),"published_at":snippet.get("publishedAt",""),"views":int(item_stats.get("viewCount",0) or 0),"url":f"https://www.youtube.com/watch?v={vid}","video_id":vid})
        return {"configured":True,"message":f"Returned {len(items)} public video results. View counts are snapshots, not proof of channel growth.","items":items}
    except Exception as exc:
        return {"configured":True,"message":f"YouTube API request failed: {exc}","items":[]}
