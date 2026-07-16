# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from .akwam_api import AkwamM3u8API
import base64
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

# المانيفست المحدث لتفعيل ممر البحث والكتالوج الذكي
MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "2.1.0",
    "name": "أكوام المحدث - Akwam HLS",
    "description": "إضافة أكوام المحدثة لمشاهدة الأفلام والمسلسلات مباشرة عبر سيرفرات التضمين",
    "resources": ["stream", "catalog"],
    "types": ["movie", "series"],
    "catalogs": [
        {
            "type": "movie",
            "id": "akwam_search_movies",
            "name": "بحث أكوام - أفلام",
            "extra": [{"name": "search", "isRequired": True}]
        },
        {
            "type": "series",
            "id": "akwam_search_series",
            "name": "بحث أكوام - مسلسلات",
            "extra": [{"name": "search", "isRequired": True}]
        }
    ],
    "idPrefixes": ["akwam:"]
}

@app.get("/manifest.json")
async def get_manifest():
    manifest_json = json.dumps(MANIFEST, ensure_ascii=False, indent=4)
    return Response(content=manifest_json, media_type="application/json; charset=utf-8")

@app.get("/catalog/{catalog_type}/{catalog_id}.json")
@app.get("/catalog/{catalog_type}/{catalog_id}/search={search_query}.json")
async def get_catalog(catalog_type: str, catalog_id: str, search_query: str = None):
    """ممر البحث: يمسح موقع أكوام ويرجع النتائج إلى ستريمو مع تشفير الروابط"""
    metas = []
    if search_query:
        # تحديد نوع البحث بناءً على قسم ستريمو (فيلم أو مسلسل)
        media_type = 'movie' if catalog_type == 'movie' else 'series'
        search_results = akwam.search(search_query, media_type=media_type)
        
        for item in search_results:
            # تشفير رابط صفحة أكوام بالكامل داخل الـ ID لتمريره بسلام إلى ممر البث
            encoded_url = base64.b64encode(item['url'].encode()).decode()
            metas.append({
                "id": f"akwam:{encoded_url}",
                "type": catalog_type,
                "name": item['name'],
                "poster": item['poster'],
                "description": f"شاهد {item['name']} مباشرة عبر سيرفرات أكوام المحدثة"
            })
            
    catalog_json = json.dumps({"metas": metas}, ensure_ascii=False, indent=4)
    return Response(content=catalog_json, media_type="application/json; charset=utf-8")

@app.get("/stream/{stream_type}/{stream_id}.json")
async def get_streams(stream_type: str, stream_id: str):
    """ممر البث: يستقبل الـ ID المشفر، ويفكه، ويقنص الـ 18 سيرفر فوراً"""
    try:
        clean_id = stream_id.replace("akwam:", "").replace(".json", "")
        
        # فك تشفير رابط أكوام الأصلي الممرر من الكتالوج
        try:
            decoded_url = base64.b64decode(clean_id.encode()).decode("utf-8")
        except Exception:
            decoded_url = clean_id

        # إذا كان المنتج مسلسلاً، نقوم بجلب الحلقات أو نمرر الرابط مباشرة للكشط
        raw_streams = akwam.extract_stream_links(decoded_url)
        
        streams = []
        for stream in raw_streams:
            streams.append({
                "name": stream["title"],
                "title": f"{stream['title']}\nQuality: Direct Embed",
                "url": stream["url"]
            })
            
        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
