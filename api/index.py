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

# المانيفست الصافي: بدون أي كتالوجات نهائياً لتبقى الواجهة نظيفة 100%
MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "3.0.0",
    "name": "أكوام الذكي - Akwam HLS",
    "description": "قنص تلقائي لـ 18 سيرفر بث مباشر بمجرد تشغيل الفيلم أو المسلسل من فورد أو ستريمو",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"] # الاستماع لمعرفات IMDB القياسية مباشرة
}

def get_media_title_from_imdb(imdb_id: str, media_type: str) -> str:
    """جلب اسم المادة بالإنجليزية صامتاً عبر Cinemeta باستخدام الـ ID"""
    try:
        # تحديد المسار المناسب بناءً على نوع المادة (فيلم أو مسلسل)
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
    """ممر البث السحري: يستقبل tt...، يبحث صامتاً، ويقنص السيرفرات فوراً"""
    try:
        # استخلاص معرف الـ IMDB الصافي (مثال: tt11003296)
        imdb_id = stream_id.replace(".json", "")
        
        # 1. جلب اسم الفيلم أو المسلسل بالإنجليزية تلقائياً
        media_title = get_media_title_from_imdb(imdb_id, stream_type)
        if not media_title:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # 2. البحث الصامت عن المادة داخل موقع أكوام عبر البروكسي
        search_results = akwam.search(media_title, media_type=stream_type)
        if not search_results:
            return Response(content=json.dumps({"streams": []}), media_type="application/json")
        
        # اختيار النتيجة الأولى المطابقة للدخول لصفحة البث
        target_page_url = search_results[0]['url']

        # 3. قنص الـ 18 سيرفر حية من خاصية data-link بناءً على تجاربنا المحلية الناجحة
        raw_streams = akwam.extract_stream_links(target_page_url)
        
        streams = []
        for stream in raw_streams:
            streams.append({
                "name": stream["title"],
                "title": f"{stream['title']}\n🌐 المستضيف: الممر السريع لـ فورد",
                "url": stream["url"]
            })
            
        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
