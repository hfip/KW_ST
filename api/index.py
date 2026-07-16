# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import requests
import json
import re

app = FastAPI(title="Stremio Akwam Addon - Watch Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# الإعدادات السحابية الجديدة والثابتة لعام 2026
CF_PROXY = "https://mbox-proxy.h-fip.workers.dev"
BASE_URL = "https://akwam.it"

MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "6.0.0",
    "name": "أكوام الذكي - Akwam Watch Direct",
    "description": "قنص تلقائي مباشر لسيرفرات البث عبر مسار المشاهدة وبدعم بروكسي كلاود فلير الخاص بـ عبد الله",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"]
}

def clean_title(title: str) -> str:
    """تنظيف الاسم من الرموز لتسهيل مطابقة البحث في أكوام"""
    title = title.lower()
    title = re.sub(r'[:\-–,.]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def get_media_title_from_cinemeta_via_cf(imdb_id: str, media_type: str) -> str:
    """جلب اسم المادة الأصلي الصافي من Cinemeta عبر البروكسي الخاص بك"""
    try:
        cinemeta_type = "movie" if media_type == "movie" else "series"
        target_url = f"https://v3-cinemeta.strem.io/meta/{cinemeta_type}/{imdb_id}.json"
        proxy_request_url = f"{CF_PROXY}/{target_url}"
        
        print(f"[🔍 Diagnostic] جاري طلب الاسم عبر البروكسي من Cinemeta للـ IMDB: {imdb_id}...")
        response = requests.get(proxy_request_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            title_en = data.get("meta", {}).get("name", "")
            if title_en:
                print(f"[✓ Diagnostic] الاسم المسترجع بنجاح هو: '{title_en}'")
                return title_en
    except Exception as e:
        print(f"[🚨 Diagnostic Error] فشل جلب الاسم عبر البروكسي: {e}")
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

        print(f"\n================ [ بداية فحص طلب البث ] ================")
        print(f"[ℹ️] النوع: {stream_type} | المعرف: {imdb_id} | الموسم: {season} | الحلقة: {episode}")

        # 1. جلب اسم المادة من Cinemeta عبر البروكسي الخاص بك
        original_title = get_media_title_from_cinemeta_via_cf(imdb_id, stream_type)
        if not original_title:
            print("[-] فشل استخراج الاسم عبر البروكسي. توقف الفحص.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # 2. إعداد الكلمات المفتاحية وتنظيفها للبحث
        search_query = clean_title(original_title)
        print(f"[🔍] الكلمة المفتاحية المستهدفة للبحث: '{search_query}'")

        # 3. محاكاة دالة البحث في أكوام عبر البروكسي (الدومين الجديد .it)
        search_section = "movie" if stream_type == "movie" else "series"
        search_url = f"{CF_PROXY}/{BASE_URL}/search?q={search_query.replace(' ', '+')}&section={search_section}"
        
        print(f"[🛰️] جاري إرسال طلب البحث الصامت إلى أكوام...")
        search_resp = requests.get(search_url, timeout=12)
        
        if search_resp.status_code != 200:
            print("[-] فشل الاتصال بأكوام عبر البروكسي.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")
            
        soup = BeautifulSoup(search_resp.text, 'html.parser')
        
        # كشط الروابط المطابقة للهيكلية الجديدة للأفلام أو المسلسلات
        media_links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if f'/{search_section}/' in href and href != f"{BASE_URL}/{search_section}/":
                if href not in media_links:
                    media_links.append(href)
                    
        if not media_links:
            print("[-] لم نجد أي نتائج مطابقة في موقع أكوام.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")
            
        target_media_url = media_links[0]
        print(f"[✓] تم العثور على رابط المادة في أكوام: {target_media_url}")
        
        # لمعالجة المسلسلات والحلقات، نقوم بتحويل الرابط إلى صفحة الحلقة المطلوبة
        if stream_type == "series":
            # إذا دخلنا صفحة المسلسل، نقوم بالتحويل المباشر لصفحة الحلقة آلياً لتوفير الطلبات
            # هيكلية حلقات أكوام الجديدة تتبع النمط: akwam.it/episode/xxxx-season-x-episode-x
            # لذا سنقوم بدخول صفحة المسلسل أولاً لقنص رابط الحلقة الصحيحة
            series_proxy_url = f"{CF_PROXY}/{target_media_url}"
            series_resp = requests.get(series_proxy_url, timeout=12)
            series_soup = BeautifulSoup(series_resp.text, 'html.parser')
            
            episode_link = None
            target_pattern = f"episode-{episode}"
            for a_tag in series_soup.find_all('a', href=True):
                if '/episode/' in a_tag['href']:
                    # التحقق من مطابقة رقم الحلقة والموسم في الرابط
                    if f"episode-{episode}" in a_tag['href'].lower() or f"الحلقة-{episode}" in a_tag['href']:
                        episode_link = a_tag['href']
                        break
            
            if episode_link:
                target_media_url = episode_link
                print(f"[🍿] تم قنص رابط الحلقة {episode} بنجاح: {target_media_url}")
            else:
                # تراجع ذكي في حال عدم تطابق التسمية العربية/الإنجليزية
                for a_tag in series_soup.find_all('a', href=True):
                    if '/episode/' in a_tag['href']:
                        target_media_url = a_tag['href']
                        break

        # 4. دخول الصفحة النهائية لقنص رابط صفحة المشاهدة watch التلقائي
        final_proxy_url = f"{CF_PROXY}/{target_media_url}"
        page_resp = requests.get(final_proxy_url, timeout=12)
        page_soup = BeautifulSoup(page_resp.text, 'html.parser')
        
        watch_link = None
        for a_tag in page_soup.find_all('a', href=True):
            if '/watch/' in a_tag['href']:
                watch_link = a_tag['href']
                break
                
        if not watch_link:
            print("[-] فشل العثور على رابط مسار المشاهدة الخفي داخل الصفحة.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")
            
        print(f"[🎯] تم قنص رابط صفحة المشاهدة بنجاح: {watch_link}")
        
        # 5. دخول صفحة watch عبر البروكسي واستخراج السيرفرات المباشرة من مشغل الفيديو Plyr
        watch_proxy_url = f"{CF_PROXY}/{watch_link}"
        watch_resp = requests.get(watch_proxy_url, timeout=12)
        
        # استخراج كافة الروابط المنتهية بـ mp4 أو m3u8 داخل السورس
        direct_sources = re.findall(r'src=["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', watch_resp.text)
        
        streams = []
        if direct_sources:
            print(f"[🔥] نجاح تام! تم استخراج {len(direct_sources)} سيرفر بث مباشر بنجاح.")
            for index, src_url in enumerate(direct_sources, 1):
                # تنظيف الرابط وفك أي مسافات
                clean_src = src_url.replace(" ", "%20")
                
                # تحديد الجودة تلقائياً من اسم الملف إن وجدت
                quality_label = "1080p" if "1080p" in clean_src else "720p" if "720p" in clean_src else "480p" if "480p" in clean_src else "Direct Stream"
                
                streams.append({
                    "name": f"🔗 سيرفر {index} [{quality_label}]",
                    "title": f"🎬 {original_title}\n⚡ جودة: {quality_label}\n🌐 المستضيف: أكوام السحابي عبر CF",
                    "url": clean_src
                })
        else:
            print("[-] لم يتم العثور على وسوم فيديو مباشرة داخل صفحة المشاهدة.")

        print(f"================ [ نهاية فحص طلب البث ] ================\n")
        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
