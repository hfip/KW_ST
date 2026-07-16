# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from .akwam_api import AkwamM3u8API
import requests
import json

app = FastAPI(title="Stremio Akwam Addon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

akwam = AkwamM3u8API()

# المانيفست متطابق تماماً وبدون أي كتالوجات لضمان بقاء الواجهة نظيفة
MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "3.1.0",
    "name": "أكوام الذكي - Akwam HLS",
    "description": "قنص تلقائي لـ 18 سيرفر بث مباشر من أكوام بناءً على الـ ID الممرر من فورد",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"]
}

def get_media_title_from_imdb(imdb_id: str, media_type: str) -> str:
    """جلب اسم المادة صامتاً وسريعاً عبر Cinemeta"""
    try:
        cinemeta_type = "movie" if media_type == "movie" else "series"
        url = f"https://v3-cinemeta.strem.io/meta/{cinemeta_type}/{imdb_id}.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("meta", {}).get("name", "")
    except Exception:
        pass
    return ""

@app.get("/manifest.json")
async def get_manifest():
    manifest_json = json.dumps(MANIFEST, ensure_ascii=False, indent=4)
    return Response(content=manifest_json, media_type="application/json; charset=utf-8")

@app.get("/stream/{stream_type}/{stream_id}.json")
async def get_streams(stream_type: str, stream_id: str):
    """ممر البث المطابق لكود FaselHD: يستقبل الـ ID، يفككه، ويبحث صامتاً ليقنص السيرفرات"""
    try:
        # تنظيف وحذف صيغة الـ json من الـ ID
        full_id = stream_id.replace(".json", "")
        
        # تفكيك المعرّف (المعرف، الموسم، الحلقة) كود FaselHD بامتياز
        parts = full_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else "1"
        episode = parts[2] if len(parts) > 2 else "1"

        # 1. جلب الاسم الإنجليزي الصافي للمادة
        media_title = get_media_title_from_imdb(imdb_id, stream_type)
        if not media_title:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # 2. البحث الصامت عبر البروكسي
        search_results = akwam.search(media_title, media_type=stream_type)
        if not search_results:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        target_page_url = None

        if stream_type == "movie":
            # للأفلام: نأخذ النتيجة الأولى مباشرة
            target_page_url = search_results[0]['url']
        else:
            # للمسلسلات: ندخل لصفحة المسلسل أولاً لجلب روابط حلقاته
            series_url = search_results[0]['url']
            episodes = akwam.get_episodes(series_url)
            
            # فلترة الحلقات للوصول للحلقة المطلوبة (المطابقة للرقم المرسل من فورد)
            target_episode_name = f"الحلقة {episode}"
            for ep in episodes:
                if target_episode_name in ep['name'] or f" {episode} " in ep['name']:
                    target_page_url = ep['url']
                    break
            
            # كخيار احتياطي إذا لم تنجح الفلترة الدقيقة، نأخذ أول حلقة متاحة
            if not target_page_url and episodes:
                target_page_url = episodes[0]['url']

        # 3. إذا عثرنا على صفحة المادة المطلوبة، نقوم بقنص روابط الـ 18 سيرفر
        streams = []
        if target_page_url:
            raw_streams = akwam.extract_stream_links(target_page_url)
            for stream in raw_streams:
                streams.append({
                    "name": stream["title"],
                    "title": f"{stream['title']}\n🌐 المستضيف: أكوام المطور",
                    "url": stream["url"]
                })

        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
