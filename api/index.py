# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .akwam_api import AkwamM3u8API
import base64

app = FastAPI(title="Stremio Akwam Addon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

akwam = AkwamM3u8API()

MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "2.0.0",
    "name": "أكوام المحدث - Akwam HLS",
    "description": "إضافة أكوام المحدثة لمشاهدة الأفلام والمسلسلات مباشرة عبر سيرفرات التضمين",
    "resources": ["stream", "catalog"],
    "types": ["movie", "series"],
    "catalogs": [
        {"type": "movie", "id": "akwam_movies", "name": "أكوام - أفلام"},
        {"type": "series", "id": "akwam_series", "name": "أكوام - مسلسلات"}
    ],
    "idPrefixes": ["akwam:"]
}

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse(content=MANIFEST)

@app.get("/catalog/{catalog_type}/{catalog_id}.json")
@app.get("/catalog/{catalog_type}/{catalog_id}/skip={skip}.json")
async def get_catalog(catalog_type: str, catalog_id: str, skip: int = 0):
    # ممر جلب الكتالوج الافتراضي أو لعرض واجهة الإضافة الأساسية
    return JSONResponse(content={"metas": []})

@app.get("/stream/{stream_type}/{stream_id}.json")
async def get_streams(stream_type: str, stream_id: str):
    """الممر المسؤول عن إرسال روابط التشغيل والـ 18 سيرفر لبرنامج Stremio"""
    try:
        # فك تشفير المعرف الممرر من ستريمو لاستخلاص الرابط الأصلي للمادة
        clean_id = stream_id.replace("akwam:", "").replace(".json", "")
        decoded_url = base64.b64decode(clean_id.encode()).decode("utf-8")
        
        # استخراج السيرفرات الحية بناءً على التكتيك الجديد
        raw_streams = akwam.extract_stream_links(decoded_url)
        
        streams = []
        for stream in raw_streams:
            streams.append({
                "name": stream["title"],
                "title": f"{stream['title']}\nQuality: Direct Embed",
                "url": stream["url"]
            })
            
        return JSONResponse(content={"streams": streams})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
