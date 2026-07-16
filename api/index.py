# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import requests
import json
import re

app = FastAPI(title="Akwam.Plex Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CF_PROXY = "https://mbox-proxy.h-fip.workers.dev"
BASE_URL = "https://akwam.it"

MANIFEST = {
    "id": "plex.abdullah.akwam.addon",
    "version": "1.0.0",
    "name": "Akwam.Plex",
    "description": "إضافة أكوام من تطوير Abdulluh.X",
    "icon": "https://raw.githubusercontent.com/hfip/Forward-MyModules/refs/heads/main/IMG_8826.jpeg",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"]
}

def clean_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r'[:\-–,.]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def get_media_title_from_cinemeta_via_cf(imdb_id: str, media_type: str) -> str:
    try:
        cinemeta_type = "movie" if media_type == "movie" else "series"
        target_url = f"https://v3-cinemeta.strem.io/meta/{cinemeta_type}/{imdb_id}.json"
        proxy_request_url = f"{CF_PROXY}/{target_url}"
        
        response = requests.get(proxy_request_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            title_en = data.get("meta", {}).get("name", "")
            if title_en:
                return title_en
    except Exception:
        pass
    return ""

@app.get("/manifest.json")
async def get_manifest():
    manifest_json = json.dumps(MANIFEST, ensure_ascii=False, indent=4)
    return Response(content=manifest_json, media_type="application/json; charset=utf-8")

@app.get("/stream/{stream_type}/{stream_id}.json")
async def get_streams(stream_type: str, stream_id: str):
    try:
        full_id = stream_id.replace(".json", "")
        parts = full_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else "1"
        episode = parts[2] if len(parts) > 2 else "1"

        original_title = get_media_title_from_cinemeta_via_cf(imdb_id, stream_type)
        if not original_title:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        search_query = clean_title(original_title)
        search_section = "movie" if stream_type == "movie" else "series"
        search_url = f"{CF_PROXY}/{BASE_URL}/search?q={search_query.replace(' ', '+')}&section={search_section}"
        
        search_resp = requests.get(search_url, timeout=12)
        if search_resp.status_code != 200:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")
            
        soup = BeautifulSoup(search_resp.text, 'html.parser')
        
        media_links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if f'/{search_section}/' in href and href != f"{BASE_URL}/{search_section}/":
                if href not in media_links:
                    media_links.append(href)
                    
        if not media_links:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")
            
        target_media_url = media_links[0]
        
        if stream_type == "series":
            series_proxy_url = f"{CF_PROXY}/{target_media_url}"
            series_resp = requests.get(series_proxy_url, timeout=12)
            series_soup = BeautifulSoup(series_resp.text, 'html.parser')
            
            episode_link = None
            for a_tag in series_soup.find_all('a', href=True):
                if '/episode/' in a_tag['href']:
                    if f"episode-{episode}" in a_tag['href'].lower() or f"الحلقة-{episode}" in a_tag['href']:
                        episode_link = a_tag['href']
                        break
            
            if episode_link:
                target_media_url = episode_link
            else:
                for a_tag in series_soup.find_all('a', href=True):
                    if '/episode/' in a_tag['href']:
                        target_media_url = a_tag['href']
                        break

        final_proxy_url = f"{CF_PROXY}/{target_media_url}"
        page_resp = requests.get(final_proxy_url, timeout=12)
        page_soup = BeautifulSoup(page_resp.text, 'html.parser')
        
        watch_link = None
        for a_tag in page_soup.find_all('a', href=True):
            if '/watch/' in a_tag['href']:
                watch_link = a_tag['href']
                break
                
        if not watch_link:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")
            
        watch_proxy_url = f"{CF_PROXY}/{watch_link}"
        watch_resp = requests.get(watch_proxy_url, timeout=12)
        
        direct_sources = re.findall(r'src=["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', watch_resp.text)
        
        streams = []
        if direct_sources:
            for index, src_url in enumerate(direct_sources, 1):
                clean_src = src_url.replace(" ", "%20")
                quality_label = "1080p" if "1080p" in clean_src else "720p" if "720p" in clean_src else "480p" if "480p" in clean_src else "Direct"
                
                streams.append({
                    "name": f"🔗 Akwam.Plex {index} [{quality_label}]",
                    "title": f"🎬 {original_title}\n⚡ جودة: {quality_label}\n🌐 Abdulluh.X Project",
                    "url": clean_src
                })

        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")

    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")
