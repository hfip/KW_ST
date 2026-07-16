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

# الـ Manifest المحدث بدون كتالوجات مع الحفاظ على الحروف العربية سليمة
MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "2.0.0",
    "name": "أكوام المحدث - Akwam HLS",
    "description": "إضافة أكوام المحدثة لمشاهدة الأفلام والمسلسلات مباشرة عبر سيرفرات التضمين",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["akwam:"]
}

@app.get("/manifest.json")
async def get_manifest():
    # استخدام Response مخصص مع ضمان عدم تحويل الحروف العربية إلى الاسكي (ASCII)
    manifest_json = json.dumps(MANIFEST, ensure_ascii=False, indent=4)
    return Response(content=manifest_json, media_type="application/json; charset=utf-8")

@app.get("/stream/{stream_type}/{stream_id}.json")
async def get_streams(stream_type: str, stream_id: str):
    """الممر المسؤول عن استقبال الطلب وفك المعرف لإعادة الـ 18 سيرفر مباشرة لستريمو"""
    try:
        # تنظيف الـ ID الممرر من ستريمو
        clean_id = stream_id.replace("akwam:", "").replace(".json", "")
        
        # محاولة فك تشفير الرابط الأصلي للمادة (Base64)
        try:
            decoded_url = base64.b64decode(clean_id.encode()).decode("utf-8")
        except Exception:
            # إذا لم يكن الرابط مشفراً بـ Base64، نتعامل معه كنص عادي (للتوافق)
            decoded_url = clean_id

        # استخراج السيرفرات الحية بناءً على التكتيك الجديد من صفحة المادة
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
