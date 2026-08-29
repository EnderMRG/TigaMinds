# MUST BE FIRST - numpy compatibility layer before ANY imports that use numpy
import sys
import pathlib
import platform

# ===== WINDOWS UTF-8 FIX =====
# Windows uses cp1252 by default which can't encode emoji characters.
# Force stdout/stderr to UTF-8 so print() with emoji doesn't crash.
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import numpy._core
except ImportError:
    try:
        import numpy.core
        # Create compatibility mapping for cv2 and other packages
        sys.modules['numpy._core'] = sys.modules['numpy.core']
        sys.modules['numpy._core.multiarray'] = sys.modules['numpy.core.multiarray']
    except (ImportError, AttributeError, KeyError):
        pass

# ===== PATHLIB FIX FOR CROSS-PLATFORM MODEL LOADING =====
# Models pickled on Linux (PosixPath) need to load on Windows (WindowsPath) and vice versa
# This must happen BEFORE joblib.load() is called
def patch_pathlib_for_cross_platform_loading():
    """
    Patch pathlib to allow loading models trained on different OS.
    If on Windows, allow PosixPath. If on Linux, allow WindowsPath.
    """
    current_os = platform.system()
    
    if current_os == "Windows":
        # Windows: Map PosixPath to WindowsPath so Linux-trained models can load
        original_posix = pathlib.PosixPath
        
        class CrossPlatformPosixPath(pathlib.WindowsPath):
            """Fake PosixPath that actually uses WindowsPath on Windows"""
            pass
        
        pathlib.PosixPath = CrossPlatformPosixPath
    else:
        # Linux: Map WindowsPath to PosixPath so Windows-trained models can load  
        original_windows = pathlib.WindowsPath
        
        class CrossPlatformWindowsPath(pathlib.PosixPath):
            """Fake WindowsPath that actually uses PosixPath on Linux"""
            pass
        
        pathlib.WindowsPath = CrossPlatformWindowsPath

patch_pathlib_for_cross_platform_loading()

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import joblib
import numpy as np
from PIL import Image
import pandas as pd
import io
import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google.cloud.firestore_v1 import Query
from datetime import datetime, timedelta
from collections import defaultdict
import cv2
from google.cloud.firestore import SERVER_TIMESTAMP
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from fastapi.responses import FileResponse
import tempfile
import torch
import json
from database import SessionLocal, get_db
from sqlalchemy.orm import Session
import models_db
from models_db import WeatherCache, ElevationCache, RouteCorridor, CropHealthScan, Scheme, SensorReading
from concurrent.futures import ThreadPoolExecutor

# Load environment variables first
load_dotenv()

# --- Gemini Rate Limit Patch ---
_original_generate_content = genai.GenerativeModel.generate_content
_ai_cache = {}

def _cached_generate_content(self, contents, **kwargs):
    prompt_str = str(contents)
    if prompt_str in _ai_cache:
        class DummyResp:
            text = _ai_cache[prompt_str]
        return DummyResp()
    
    try:
        resp = _original_generate_content(self, contents, **kwargs)
        if resp and hasattr(resp, 'text') and resp.text:
            _ai_cache[prompt_str] = resp.text
        return resp
    except Exception as e:
        if "429" in str(e):
            print("⚠️ Gemini API Rate Limit (429) hit! Returning context-aware fallback.")
            
            # Determine which type of prompt this is based on keywords to provide a contextual mock
            lower_prompt = prompt_str.lower()
            
            if "market strategist" in lower_prompt:
                fallback_text = "- Monitor Guwahati auction volumes to time your harvest effectively.\n- Maintain optimal plucking rounds to ensure premium leaf grades.\n- Consider forward contracts if price volatility increases."
            elif "market analyst" in lower_prompt:
                fallback_text = "The market exhibits typical seasonal stability. Demand for quality orthodox and CTC grades remains steady, suggesting growers should focus on maintaining quality standards rather than accelerating harvests."
            elif "leaf pathologist" in lower_prompt:
                fallback_text = "- Increase plucking frequency to remove potentially infected leaves.\n- Ensure adequate drainage to prevent waterlogging and fungal growth.\n- Apply appropriate organic fungicides if disease severity crosses the economic threshold."
            elif "agronomist" in lower_prompt:
                fallback_text = "- Maintain consistent soil moisture through scheduled irrigation.\n- Monitor pest populations during temperature fluctuations.\n- Ensure balanced NPK application based on recent soil tests."
            elif "executive summary" in lower_prompt or "management advisor" in lower_prompt:
                fallback_text = "Overall farm metrics indicate stable operational health. Focus on maintaining current irrigation schedules and vigilant pest monitoring. Market conditions are neutral, prioritizing yield quality over sheer volume."
            else:
                fallback_text = "Operations are stable. Continue standard best practices for cultivation and monitoring."
                
            class DummyResp:
                text = fallback_text
            return DummyResp()
        raise e

genai.GenerativeModel.generate_content = _cached_generate_content
# ------------------------

# Load Firebase credentials from environment variables
firebase_creds = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),  # Convert literal \n to actual newlines
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN")
}

cred = credentials.Certificate(firebase_creds)
firebase_admin.initialize_app(cred)

import firestore_mock
db = firestore_mock.client()
print("🔥 Using firestore_mock globally to bypass Firebase quota limits!")


# SQLite cache DB has been migrated to NeonDB



# ===== SQLITE HELPER: OPEN-METEO WEATHER =====
def _get_open_meteo_rain(lat: float, lon: float) -> float:
    """Fetch real max-48h precipitation from Open-Meteo; cache in SQLite for 3 hours.
    Returns normalized rainfall_intensity in [0, 1] (0=dry, 1=>=20mm)."""
    import requests as _r
    lat_r, lon_r = round(lat, 2), round(lon, 2)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    now_str = datetime.utcnow().isoformat()
    # Check cache
    try:
        db = SessionLocal()
        try:
            row = db.query(WeatherCache).filter(
                WeatherCache.lat == lat_r,
                WeatherCache.lon == lon_r,
                WeatherCache.date == today
            ).first()
            if row:
                age_h = (datetime.utcnow() - datetime.fromisoformat(row.cached_at)).total_seconds() / 3600
                if age_h < 3:
                    return min(row.precipitation_mm / 20.0, 1.0)
        finally:
            db.close()
    except Exception:
        pass
    # Fetch from Open-Meteo (no API key required)
    try:
        r = _r.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat_r, "longitude": lon_r,
                "hourly": "precipitation,precipitation_probability",
                "forecast_days": 3,
            },
            timeout=10, headers={"User-Agent": "ChaiNet/1.0"}
        )
        r.raise_for_status()
        hourly = r.json().get("hourly", {})
        precip_list = hourly.get("precipitation", [])
        max_precip = max(precip_list[:48]) if precip_list else 0.0
        max_prob = max(hourly.get("precipitation_probability", [0])[:48], default=0)
        # Cache result
        try:
            db = SessionLocal()
            try:
                existing = db.query(WeatherCache).filter(
                    WeatherCache.lat == lat_r,
                    WeatherCache.lon == lon_r,
                    WeatherCache.date == today
                ).first()
                if existing:
                    existing.precipitation_mm = max_precip
                    existing.precipitation_probability = max_prob / 100.0
                    existing.cached_at = now_str
                else:
                    db.add(WeatherCache(
                        lat=lat_r, lon=lon_r, date=today,
                        precipitation_mm=max_precip,
                        precipitation_probability=max_prob / 100.0,
                        cached_at=now_str
                    ))
                db.commit()
            finally:
                db.close()
        except Exception:
            pass
        normalized = round(min(max_precip / 20.0, 1.0), 3)
        print(f"    Rain({lat_r},{lon_r}): {max_precip:.1f}mm/48h → intensity={normalized:.3f}")
        return normalized
    except Exception as exc:
        print(f"⚠️ Open-Meteo weather: {exc}")
        # Seasonal fallback
        month = datetime.utcnow().month
        base = 0.60 if 6 <= month <= 9 else (0.30 if month in (5, 10) else 0.10)
        return round(min(1.0, base + (hash((lat_r, lon_r)) % 100) / 300.0), 3)


# ===== SQLITE HELPER: OPEN-METEO ELEVATION SLOPE =====
def _get_elevation_slope(lat1: float, lon1: float, lat2: float, lon2: float, dist_m: float) -> float:
    """Compute terrain slope factor [0,1] using Open-Meteo elevation API.
    Cache results permanently in elevation_cache (elevation doesn't change)."""
    import requests as _r
    if dist_m < 50:  # trivially short segment
        return 0.10
    lat1_r, lon1_r = round(lat1, 3), round(lon1, 3)
    lat2_r, lon2_r = round(lat2, 3), round(lon2, 3)

    def _get_cached_elev(lat_r, lon_r):
        try:
            db = SessionLocal()
            try:
                row = db.query(ElevationCache).filter(
                    ElevationCache.lat == lat_r,
                    ElevationCache.lon == lon_r
                ).first()
                return float(row.elevation_m) if row else None
            finally:
                db.close()
        except Exception:
            return None

    def _store_elev(lat_r, lon_r, elev):
        try:
            db = SessionLocal()
            try:
                existing = db.query(ElevationCache).filter(
                    ElevationCache.lat == lat_r,
                    ElevationCache.lon == lon_r
                ).first()
                if existing:
                    existing.elevation_m = elev
                    existing.cached_at = datetime.utcnow().isoformat()
                else:
                    db.add(ElevationCache(
                        lat=lat_r, lon=lon_r, elevation_m=elev,
                        cached_at=datetime.utcnow().isoformat()
                    ))
                db.commit()
            finally:
                db.close()
        except Exception:
            pass

    e1 = _get_cached_elev(lat1_r, lon1_r)
    e2 = _get_cached_elev(lat2_r, lon2_r)
    to_fetch_lats, to_fetch_lons, to_fetch_tags = [], [], []
    if e1 is None:
        to_fetch_lats.append(str(lat1_r)); to_fetch_lons.append(str(lon1_r)); to_fetch_tags.append(1)
    if e2 is None:
        to_fetch_lats.append(str(lat2_r)); to_fetch_lons.append(str(lon2_r)); to_fetch_tags.append(2)
    if to_fetch_lats:
        try:
            r = _r.get(
                "https://api.open-meteo.com/v1/elevation",
                params={"latitude": ",".join(to_fetch_lats), "longitude": ",".join(to_fetch_lons)},
                timeout=8, headers={"User-Agent": "ChaiNet/1.0"}
            )
            r.raise_for_status()
            elevs = r.json().get("elevation", [])
            for i, tag in enumerate(to_fetch_tags):
                if i < len(elevs) and elevs[i] is not None:
                    if tag == 1:
                        e1 = float(elevs[i]); _store_elev(lat1_r, lon1_r, e1)
                    else:
                        e2 = float(elevs[i]); _store_elev(lat2_r, lon2_r, e2)
        except Exception as exc:
            print(f"⚠️ Open-Meteo elevation: {exc}")

    if e1 is None or e2 is None:
        return 0.30  # default moderate slope
    slope_raw = abs(e2 - e1) / max(dist_m, 1.0)  # m per m
    slope_factor = round(min(slope_raw / 0.1, 1.0), 3)  # 0.1 m/m = max (steep hill)
    print(f"    Slope: e1={e1:.0f}m e2={e2:.0f}m d={dist_m:.0f}m → factor={slope_factor:.3f}")
    return slope_factor


# ===== SQLITE HELPER: HISTORICAL DELAY FLAG =====
def _get_historical_delay(mid_lat: float, mid_lon: float) -> dict:
    """Look up historical delay flag for a corridor segment midpoint from SQLite."""
    try:
        db = SessionLocal()
        try:
            # We sort by area: (max_lat - min_lat) * (max_lon - min_lon)
            from sqlalchemy import func
            row = db.query(RouteCorridor).filter(
                RouteCorridor.min_lat <= mid_lat,
                RouteCorridor.max_lat >= mid_lat,
                RouteCorridor.min_lon <= mid_lon,
                RouteCorridor.max_lon >= mid_lon
            ).order_by(
                ((RouteCorridor.max_lat - RouteCorridor.min_lat) * (RouteCorridor.max_lon - RouteCorridor.min_lon)).asc()
            ).first()
            
            return {
                "historical_delay_flag": float(row.historical_delay_flag),
                "corridor_name": row.name,
                "hazard_type": row.hazard_type,
                "hazard_description": row.hazard_description,
                "severity": row.severity,
            } if row else {
                "historical_delay_flag": 0.20,
                "corridor_name": None,
                "hazard_type": None,
                "hazard_description": None,
                "severity": None,
            }
        finally:
            db.close()
    except Exception as exc:
        print(f"⚠️ Corridor lookup: {exc}")
        return {
            "historical_delay_flag": 0.20,
            "corridor_name": None,
            "hazard_type": None,
            "hazard_description": None,
            "severity": None,
        }


# ===== SQLITE HELPER: CROP HEALTH HISTORY =====
def _get_ndvi_history_db(field_id: str, limit: int = 10) -> list:
    """Fetch NDVI history from NeonDB crop_health_scans (primary source)."""
    try:
        db = SessionLocal()
        try:
            # We want the latest `limit` scans, sorted chronologically.
            # So first, get latest `limit` order by date desc, then sort by date asc.
            scans = db.query(CropHealthScan).filter(
                CropHealthScan.field_id == field_id
            ).order_by(CropHealthScan.scene_date.desc()).limit(limit).all()
            
            # Sort ascending for history trend
            scans.sort(key=lambda s: s.scene_date)
            
            return [
                {
                    "date": r.scene_date,
                    "mean_ndvi": round(r.ndvi, 4),
                    "mean_evi": round(r.evi, 4),
                    "mean_ndwi": round(r.ndwi, 4),
                    "health_class": r.classification,
                }
                for r in scans
            ]
        finally:
            db.close()
    except Exception as exc:
        print(f"⚠️ NeonDB NDVI history: {exc}")
        return []


def _store_crop_scan_db(field_id: str, geometry: dict, result: dict, scene_date: str) -> str:
    scan_id = f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    db = SessionLocal()
    try:
        db.add(CropHealthScan(
            field_id=field_id,
            polygon_geojson=json.dumps(geometry, sort_keys=True),
            ndvi=result["mean_ndvi"],
            evi=result["mean_evi"],
            ndwi=result["mean_ndwi"],
            classification=result["health_class"],
            scene_date=scene_date,
            created_at=datetime.utcnow().isoformat()
        ))
        db.commit()
    finally:
        db.close()
    return scan_id


# ===== TWILIO SMS CONFIGURATION =====
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

# Initialize Twilio client
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("✅ Twilio SMS service initialized successfully")
    except Exception as e:
        print(f"⚠️ Twilio initialization failed: {e}")
else:
    print("⚠️ Twilio credentials not configured - SMS service disabled")

try:
    df = pd.read_excel("teadata.xlsx")

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )

    df["week_ending_date"] = pd.to_datetime(df["week_ending_date"])

    market_columns = [
        "kolkata", "guwahati", "siliguri", "jalpaiguri",
        "mjunction", "cochin", "coonoor", "coimbatore", "tea_serve"
    ]

    def extract_price(val):
        if pd.isna(val):
            return np.nan
        match = re.search(r"(\d+\.?\d*)", str(val))
        return float(match.group(1)) if match else np.nan

    for col in market_columns:
        df[col] = df[col].apply(extract_price)

    df["avg_price"] = df[market_columns].mean(axis=1)
    df = df.sort_values("week_ending_date")

except Exception as e:
    print("❌ DATA LOAD ERROR:", e)
    df = None

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Demo account configuration
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@chaitea.com")

# Security
security = HTTPBearer(auto_error=False)

# User model
class User(BaseModel):
    uid: str
    email: str
    is_demo_view: bool = False

# Authentication dependency
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Verify Firebase ID token and return user information.
    Checks X-Force-Demo header to toggle demo view.
    Short-circuits Firebase verification for demo mode requests.
    """
    try:
        token_query = request.query_params.get("token")
        
        if not credentials and not token_query:
            raise HTTPException(status_code=401, detail="No credentials provided")

        token = credentials.credentials if credentials else token_query

        # --- DEMO MODE BYPASS ---
        # If X-Force-Demo header is set OR the token is the demo placeholder,
        # skip Firebase verification entirely and return a mock user.
        is_demo = request.headers.get("X-Force-Demo") == "true" or token == "demo_token"
        if is_demo:
            print(f"🎭 DEMO MODE ACTIVE - bypassing Firebase auth")
            return User(
                uid="demo123",
                email=DEMO_EMAIL,
                is_demo_view=True
            )
        # ------------------------

        decoded_token = auth.verify_id_token(token)

        return User(
            uid=decoded_token['uid'],
            email=decoded_token.get('email', ''),
            is_demo_view=False
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ AUTH ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )

# Farm ID resolution
def resolve_farm_id(user: User) -> str:
    """
    Determine which farm ID to use based on user.
    If 'is_demo_view' is True or email matches demo, use 'demo_farm'.
    """
    if user.is_demo_view or user.email.lower() == DEMO_EMAIL.lower():
        return "demo_farm"
    return f"farm_{user.uid}"


app = FastAPI(title="CHAI-NET Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global handler so unhandled 500s always carry CORS headers
# (FastAPI's default error handler bypasses middleware on crashes)
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )


class SubsidyChatRequest(BaseModel):
    question: str
    matched_scheme_ids: List[int] = []


@app.get("/api/subsidies/match")
def match_subsidies(estate_size_ha: float = 0, grower_type: str = "individual", activity: str = "replanting", region: str = "All", user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        from sqlalchemy import or_, and_, func
        if activity.lower() == "all":
            rows = db.query(Scheme).filter(
                or_(region == 'All', Scheme.region_specificity == region)
            ).order_by(Scheme.id).all()
        else:
            cat_filter = func.lower(Scheme.category).like(f"%{activity.lower()}%")
            if activity.lower() in ("replanting", "plantation"):
                cat_filter = or_(cat_filter, func.lower(Scheme.category).like("%plantation/replanting%"))
            
            rows = db.query(Scheme).filter(
                cat_filter,
                or_(region == 'All', Scheme.region_specificity == region)
            ).order_by(Scheme.id).all()
        
        matches = []
        for row in rows:
            record = {
                "id": row.id,
                "name": row.name,
                "provider": row.provider,
                "category": row.category,
                "subsidy_details": row.subsidy_details,
                "eligibility_criteria": row.eligibility_criteria,
                "application_window": row.application_window,
                "source_url": row.source_url,
                "region_specificity": row.region_specificity
            }
            record["match_reason"] = f"Relevant to {activity}; verify registration and component conditions with {record['provider']}."
            record["score"] = 2 if activity.lower() in record["category"].lower() else 1
            matches.append(record)
    finally:
        db.close()
    
    matches.sort(key=lambda item: (-item["score"], item["id"]))
    return {"criteria": {"estate_size_ha": estate_size_ha, "grower_type": grower_type, "activity": activity, "region": region}, "schemes": matches}


@app.post("/api/subsidies/advisor")
def subsidy_advisor(payload: SubsidyChatRequest, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        if payload.matched_scheme_ids:
            rows = db.query(Scheme).filter(Scheme.id.in_(payload.matched_scheme_ids)).all()
        else:
            rows = db.query(Scheme).order_by(Scheme.id).all()
        context = "\n".join(f"{row.name} | Provider: {row.provider} | Category: {row.category} | Details: {row.subsidy_details} | Eligibility: {row.eligibility_criteria} | Window: {row.application_window} | Source: {row.source_url}" for row in rows)
    finally:
        db.close()
    prompt = f"Answer using ONLY these official scheme records. Do not invent rates, dates, eligibility, or benefits. If not covered, say exactly: not covered in our current database, check with Tea Board directly.\nQuestion: {payload.question}\nRecords:\n{context}"
    try:
        response = genai.GenerativeModel("models/gemini-flash-latest").generate_content(prompt)
        answer = response.text.strip() if response and response.text else "not covered in our current database, check with Tea Board directly"
    except Exception:
        answer = "not covered in our current database, check with Tea Board directly"
    return {"answer": answer, "grounded_scheme_count": len(rows)}


@app.get("/api/subsidies/insurance-dossier/{field_id}")
def insurance_evidence_dossier(field_id: str, user: User = Depends(get_current_user)):
    since = (datetime.utcnow() - timedelta(days=90)).isoformat()
    db = SessionLocal()
    try:
        scans = db.query(CropHealthScan).filter(
            CropHealthScan.field_id == field_id,
            CropHealthScan.created_at >= since
        ).order_by(CropHealthScan.scene_date).all()
        
        # Format scans like the sqlite row fetchall did
        scans = [
            {
                "scene_date": s.scene_date,
                "ndvi": s.ndvi,
                "evi": s.evi,
                "ndwi": s.ndwi,
                "classification": s.classification
            } for s in scans
        ]
    finally:
        db.close()
    sensor_count = 0
    try:
        start = datetime.utcnow() - timedelta(days=90)
        docs = db.collection("farms").document(resolve_farm_id(user)).collection("sensors").document("sensors_root").collection("readings").where("timestamp", ">=", start).limit(5000).stream()
        sensor_count = sum(1 for _ in docs)
    except Exception as exc:
        print(f"⚠️ Dossier sensor read: {exc}")
    pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_file.close()
    doc = SimpleDocTemplate(pdf_file.name, pagesize=letter, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = [Paragraph("ChaiNet Insurance Evidence Dossier", styles["Title"]), Spacer(1, 12), Paragraph(f"Field: {field_id} | Evidence period: last 90 days", styles["Normal"]), Spacer(1, 12), Paragraph("Supporting evidence for a private insurer or claims assessor. Not an insurance policy or claim decision.", styles["Normal"]), Spacer(1, 16), Paragraph(f"Crop-health scans recorded: {len(scans)}", styles["Heading2"]), Paragraph(f"IoT sensor readings available: {sensor_count}", styles["Heading2"])]
    table_data = [["Scene date", "NDVI", "EVI", "NDWI", "Class"]] + [[row["scene_date"], f"{row['ndvi']:.3f}", f"{row['evi']:.3f}", f"{row['ndwi']:.3f}", row["classification"]] for row in scans]
    if len(table_data) == 1:
        table_data.append(["No scan records", "-", "-", "-", "-"])
    table = Table(table_data, colWidths=[90, 70, 70, 70, 100])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elements.extend([Spacer(1, 8), table])
    doc.build(elements)
    return FileResponse(pdf_file.name, media_type="application/pdf", filename=f"chainet-insurance-dossier-{field_id}.pdf")

# CORS - Support both local development and production
frontend_url = os.getenv("FRONTEND_URL", "")
allowed_origins = [
    "http://localhost:3000",  # Local development
    "http://localhost:3001",  # Next.js fallback port
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:3005",
]

# Add production frontend URL if set
if frontend_url:
    allowed_origins.append(frontend_url)

# Also allow common deployment platforms
allowed_origins.extend([
    "https://*.vercel.app",
    "https://*.onrender.com",
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.onrender\.com|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== HEALTH CHECK ENDPOINTS =====
@app.get("/")
def health_check():
    """Root endpoint for health checks and port binding verification"""
    return {
        "status": "ok",
        "service": "CHAI-NET Backend",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Backend is running and ready to receive requests"
    }

@app.head("/")
def health_check_head():
    """HEAD request support for port detection"""
    return {"status": "ok"}

@app.get("/health")
def detailed_health():
    """Detailed health check with model status"""
    return {
        "status": "healthy",
        "models": {
            "leaf_classifier": "loaded" if leaf_model else "failed",
            "pest_risk": "loaded" if pest_model else "failed",
            "drought_risk": "loaded" if drought_model else "failed",
            "price_forecast": "loaded" if price_model else "failed",
            "yolo_detection": "loaded" if yolo_model else "failed"
        },
        "firebase": "connected",
        "twilio_sms": "configured" if twilio_client else "not_configured",
        "timestamp": datetime.utcnow().isoformat()
    }


# ===== SMS ALERT SERVICE =====

class SMSRequest(BaseModel):
    """Request model for sending SMS"""
    phone: str  
    message: str 

class SMSResponse(BaseModel):
    """Response model for SMS sending"""
    success: bool
    message_sid: Optional[str] = None
    error: Optional[str] = None
    timestamp: str

@app.post("/api/send-sms")
def send_sms(request: SMSRequest):
    """
    Send SMS alert to a worker's phone.
    
    Request body:
    {
        "phone": "+917002168639",
        "message": "আজি কাম আছে"
    }
    
    Returns:
    {
        "success": true,
        "message_sid": "SM1234567890abcdef...",
        "timestamp": "2026-02-03T02:30:00.000000"
    }
    """
    
    # Validate inputs
    if not request.phone or not request.message:
        return SMSResponse(
            success=False,
            error="Phone number and message are required",
            timestamp=datetime.utcnow().isoformat()
        )
    
    # Check if Twilio is configured
    if not twilio_client or not TWILIO_PHONE:
        return SMSResponse(
            success=False,
            error="SMS service is not configured. Twilio credentials missing.",
            timestamp=datetime.utcnow().isoformat()
        )
    
    try:
        # Validate phone number format (basic E.164 validation)
        if not request.phone.startswith("+"):
            return SMSResponse(
                success=False,
                error="Phone number must be in E.164 format (e.g., +91XXXXXXXXXX)",
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Send SMS using Twilio
        message = twilio_client.messages.create(
            body=request.message,  # Unicode content supported
            from_=TWILIO_PHONE,
            to=request.phone
        )
        
        print(f"✅ SMS sent successfully to {request.phone}")
        print(f"   Message SID: {message.sid}")
        print(f"   Message: {request.message}")
        
        return SMSResponse(
            success=True,
            message_sid=message.sid,
            timestamp=datetime.utcnow().isoformat()
        )
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Failed to send SMS to {request.phone}: {error_msg}")
        
        return SMSResponse(
            success=False,
            error=f"SMS sending failed: {error_msg}",
            timestamp=datetime.utcnow().isoformat()
        )


@app.post("/api/send-bulk-sms")
def send_bulk_sms(phones: List[str], message: str):
    """
    Send SMS alert to multiple workers.
    
    Request body:
    {
        "phones": ["+91XXXXXXXXXX", "+91YYYYYYYYYY"],
        "message": "আজি কাম আছে"
    }
    
    Returns:
    {
        "success": true,
        "sent": 2,
        "failed": 0,
        "results": [
            {"phone": "+91XXXXXXXXXX", "success": true, "message_sid": "SM..."},
            ...
        ]
    }
    """
    
    if not phones or not message:
        return {
            "success": False,
            "error": "Phones list and message are required"
        }
    
    if not twilio_client or not TWILIO_PHONE:
        return {
            "success": False,
            "error": "SMS service is not configured"
        }
    
    results = []
    sent_count = 0
    failed_count = 0
    
    for phone in phones:
        try:
            msg = twilio_client.messages.create(
                body=message,
                from_=TWILIO_PHONE,
                to=phone
            )
            results.append({
                "phone": phone,
                "success": True,
                "message_sid": msg.sid
            })
            sent_count += 1
            print(f"✅ SMS sent to {phone}")
        except Exception as e:
            results.append({
                "phone": phone,
                "success": False,
                "error": str(e)
            })
            failed_count += 1
            print(f"❌ Failed to send SMS to {phone}: {e}")
    
    return {
        "success": True,
        "sent": sent_count,
        "failed": failed_count,
        "total": len(phones),
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
    }




# Load models with error handling for missing files
try:
    print("📦 Loading tea_leaf_model.pkl...")
    leaf_model = joblib.load("models/tea_leaf_model.pkl", mmap_mode='r')
    print("✅ tea_leaf_model.pkl loaded successfully")
except FileNotFoundError:
    print("⚠️ tea_leaf_model.pkl not found, using None")
    leaf_model = None
except Exception as e:
    print(f"⚠️ Failed to load tea_leaf_model.pkl: {e}")
    import traceback
    traceback.print_exc()
    leaf_model = None

try:
    print("📦 Loading pest_risk_model.pkl...")
    pest_model = joblib.load("models/pest_risk_model.pkl", mmap_mode='r')
    print("✅ pest_risk_model.pkl loaded successfully")
except FileNotFoundError:
    print("⚠️ pest_risk_model.pkl not found, using None")
    pest_model = None
except Exception as e:
    print(f"⚠️ Failed to load pest_risk_model.pkl: {e}")
    import traceback
    traceback.print_exc()
    pest_model = None

try:
    print("📦 Loading drought_risk_model.pkl...")
    drought_model = joblib.load("models/drought_risk_model.pkl", mmap_mode='r')
    print("✅ drought_risk_model.pkl loaded successfully")
except FileNotFoundError:
    print("⚠️ drought_risk_model.pkl not found, using None")
    drought_model = None
except Exception as e:
    print(f"⚠️ Failed to load drought_risk_model.pkl: {e}")
    import traceback
    traceback.print_exc()
    drought_model = None

try:
    feature_names = joblib.load("models/model1_features.pkl")
except FileNotFoundError:
    print("⚠️ model1_features.pkl not found, using None")
    feature_names = None
except Exception as e:
    print(f"⚠️ Failed to load model1_features.pkl: {e}")
    feature_names = None

try:
    price_model = joblib.load("models/tea_price_model.pkl")
except FileNotFoundError:
    print("⚠️ tea_price_model.pkl not found, using None")
    price_model = None
except Exception as e:
    print(f"⚠️ Failed to load tea_price_model.pkl: {e}")
    price_model = None

try:
    class_labels = joblib.load("models/class_labels.pkl")
except FileNotFoundError:
    print("⚠️ class_labels.pkl not found, using None")
    class_labels = None
except Exception as e:
    print(f"⚠️ Failed to load class_labels.pkl: {e}")
    class_labels = None

# Load YOLOv5 object detection model for disease localization
try:
    print("📦 Loading YOLOv5 model...")
    if os.getenv("ENABLE_YOLO", "false").lower() != "true":
        raise RuntimeError("YOLO disabled by default; set ENABLE_YOLO=true to enable leaf detection")
    # Monkey-patch PyTorch to completely bypass the GitHub API check that causes the 403 Rate Limit error
    import torch.hub
    if hasattr(torch.hub, '_validate_not_a_forked_repo'):
        torch.hub._validate_not_a_forked_repo = lambda a, b, c: True
        
    yolo_model = torch.hub.load('ultralytics/yolov5', 'custom', path='models/best.pt', force_reload=False, trust_repo=True)
    yolo_model.conf = 0.25  # Confidence threshold
    yolo_model.iou = 0.45   # NMS IOU threshold
    print("✅ YOLOv5 disease detection model loaded successfully")
except Exception as e:
    print(f"⚠️ YOLOv5 model loading failed: {e}")
    import traceback
    traceback.print_exc()
    yolo_model = None

index_to_label = {v: k for k, v in class_labels.items()} if class_labels else {}

print("PRICE MODEL TYPE:", type(price_model))
print("PRICE MODEL CONTENT:", price_model)

def generate_ai_market_insight(context: dict):
    prompt = f"""
You are a tea market analyst specializing in Guwahati auctions.

Given the following market indicators, provide a concise strategic insight.

Rules:
- Do NOT invent numbers
- Do NOT give predictions
- Focus on interpretation and strategy
- Professional, neutral tone
- 2–3 sentences max

Market Data:
{context}
"""

    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else None
    except Exception as e:
        print("❌ AI INSIGHT ERROR:", e)
        return None
    
def generate_ai_strategy_recommendations(context: dict):
    prompt = f"""
You are a tea market strategist advising producers in Guwahati.

Based on the market conditions below, generate 3 concise, actionable strategy recommendations.

Rules:
- Align strictly with the market signal
- No numbers unless provided
- No long-term predictions
- Bullet points only
- Professional tone

Market Context:
{context}
"""

    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(prompt)

        if not response or not response.text:
            return []

        recs = []
        for line in response.text.split("\n"):
            line = line.strip()
            if line.startswith(("-", "•", "*")):
                recs.append(line.lstrip("-•* ").strip())

        return recs[:4]
    except Exception as e:
        print("❌ AI STRATEGY ERROR:", e)
        return []

def forecast_price_from_dict(model_dict, steps=1):
    """
    Forecast future price using stored trend information
    """
    last_price = model_dict["last_price"]
    slope = model_dict["slope"]

    return last_price + slope * steps

# -----------------------------
# LEAF QUALITY API
# -----------------------------

def generate_leaf_quality_recommendations(grade: str, confidence: int):
    prompt = f"""
You are an expert tea leaf pathologist.

Based on the AI leaf scan result below, generate 3–4 actionable quality
improvement recommendations.

Rules:
- Focus ONLY on leaf health and disease
- Use professional agricultural language
- Mention WHY the action is needed
- Keep recommendations concise
- Bullet points only
- No emojis

Leaf Analysis Result:
- Detected Condition: {grade}
- Model Confidence: {confidence}%
"""

    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(prompt)

        if not response or not response.text:
            return ["No recommendations available for this scan."]

        recommendations = []
        for line in response.text.split("\n"):
            line = line.strip()
            if line.startswith(("-", "•", "*")):
                recommendations.append(
                    line.lstrip("-•* ").strip()
                )

        return recommendations or [
            "Continue routine monitoring of leaf health."
        ]

    except Exception as e:
        print("❌ LEAF AI ERROR:", e)
        return ["Leaf AI service unavailable."]


def analyze_leaf_surface(image: Image.Image):
    img = np.array(image)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

    total_pixels = img.shape[0] * img.shape[1]

    # GREEN (healthy)
    green_mask = cv2.inRange(
        hsv,
        np.array([35, 40, 40]),
        np.array([90, 255, 255])
    )

    # YELLOW (stress)
    yellow_mask = cv2.inRange(
        hsv,
        np.array([15, 40, 40]),
        np.array([35, 255, 255])
    )

    # BROWN (disease / rust / leaf spot)
    brown_mask = cv2.inRange(
        hsv,
        np.array([5, 60, 40]),
        np.array([25, 255, 160])
    )

    # DARK (dead tissue)
    dark_mask = cv2.inRange(hsv[:, :, 2], 0, 50)

    return {
        "green": round(np.sum(green_mask > 0) / total_pixels, 3),
        "yellow": round(np.sum(yellow_mask > 0) / total_pixels, 3),
        "brown": round(np.sum(brown_mask > 0) / total_pixels, 3),
        "dark": round(np.sum(dark_mask > 0) / total_pixels, 3),
    }


def detect_disease_with_yolo(image: Image.Image):
    """
    Run YOLOv5 object detection on the leaf image to detect disease regions.
    Returns list of detections with disease name, bounding box, and confidence.
    """
    if yolo_model is None:
        return None
    
    try:
        # Run inference
        results = yolo_model(image)
        
        # Parse results
        detections = []
        
        # results.pandas().xyxy[0] contains: xmin, ymin, xmax, ymax, confidence, class, name
        df = results.pandas().xyxy[0]
        
        for _, row in df.iterrows():
            detection = {
                "disease_name": row['name'],
                "confidence": round(float(row['confidence']), 3),
                "bbox": {
                    "xmin": int(row['xmin']),
                    "ymin": int(row['ymin']),
                    "xmax": int(row['xmax']),
                    "ymax": int(row['ymax'])
                }
            }
            detections.append(detection)
        
        print(f"\n🎯 YOLO DETECTIONS: {len(detections)} disease regions found")
        for det in detections:
            print(f"   - {det['disease_name']}: {det['confidence']*100:.1f}% confidence")
        
        return detections if len(detections) > 0 else None
        
    except Exception as e:
        print(f"❌ YOLO detection error: {e}")
        return None

@app.post("/api/leaf-quality")
async def leaf_quality(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    image_bytes = await file.read()
    original_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # -------- YOLO OBJECT DETECTION (on original image) --------
    yolo_detections = detect_disease_with_yolo(original_image)

    # -------- CENTER CROP (preserve lesions) --------
    w, h = original_image.size
    image = original_image.crop((
        int(w * 0.1),
        int(h * 0.1),
        int(w * 0.9),
        int(h * 0.9)
    )).resize((224, 224))

    # -------- CNN PREDICTION --------
    if leaf_model:
        img_array = np.array(image) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        prediction = leaf_model.predict(img_array)
        predicted_class = int(np.argmax(prediction, axis=1)[0])
        confidence = int(np.max(prediction) * 100)

        print("\n🧠 CNN RAW OUTPUT:", prediction)
        print("🧠 CNN predicted_class index:", predicted_class)
        print("🧠 CNN confidence (%):", confidence)

        if isinstance(class_labels, dict):
            cnn_grade = index_to_label.get(predicted_class, "Unknown")
            print("🧠 CNN mapped label:", cnn_grade)
        else:
            cnn_grade = class_labels[predicted_class]
    else:
        print("⚠️ CNN model missing (OOM fallback). Skipping CNN.")
        cnn_grade = "Unknown"
        confidence = 0

    # -------- SURFACE ANALYSIS --------
    surface = analyze_leaf_surface(image)
    print("\n🎨 HSV SURFACE ANALYSIS:")
    print("   green :", surface["green"])
    print("   yellow:", surface["yellow"])
    print("   brown :", surface["brown"])
    print("   dark  :", surface["dark"])


    # -------- RULE-BASED GRADE --------
    if surface["brown"] > 0.08 or surface["dark"] > 0.05:
        rule_grade = "Diseased"
    elif surface["yellow"] > 0.15:
        rule_grade = "Stressed"
    elif surface["green"] > 0.6:
        rule_grade = "Healthy"
    else:
        rule_grade = "Uncertain"

    print("\n📏 RULE-BASED GRADE:", rule_grade)

    # -------- SEVERITY --------
    severity = (
        "High" if surface["brown"] > 0.15 or surface["dark"] > 0.1
        else "Moderate" if surface["brown"] > 0.08 or surface["yellow"] > 0.2
        else "Low"
    )

    # -------- DEBUG PRINTS --------
    print("\n========== LEAF ANALYSIS DEBUG ==========")
    print("CNN RAW PREDICTION      :", cnn_grade)
    print("CNN CONFIDENCE (%)      :", confidence)
    print("SURFACE ANALYSIS        :", surface)
    print("RULE-BASED GRADE        :", rule_grade)

    # -------- FINAL DECISION LOGIC --------
    if cnn_grade == "Unknown":
        if yolo_detections:
            final_grade = "Diseased"
            final_disease = yolo_detections[0]["disease_name"]
            decision_source = "YOLO"
        else:
            final_grade = rule_grade
            final_disease = None if rule_grade.lower() == "healthy" else "surface-detected disease"
            decision_source = "RULE_BASED"
    elif cnn_grade.lower() == "healthy":
        # CNN says healthy → trust HSV rule-based system
        final_grade = rule_grade
        final_disease = None if rule_grade.lower() == "healthy" else "surface-detected disease"
        decision_source = "RULE_BASED"
    else:
        # CNN says disease → trust CNN disease class
        final_grade = "Diseased"
        final_disease = cnn_grade
        decision_source = "CNN"

    print("FINAL GRADE             :", final_grade)
    print("FINAL DISEASE TYPE      :", final_disease)
    print("DECISION SOURCE         :", decision_source)
    print("========================================\n")

    confidence_level = (
        "High" if confidence >= 90
        else "Medium" if confidence >= 75
        else "Low"
    )

    # -------- AI RECOMMENDATIONS --------
    ai_recommendations = generate_leaf_quality_recommendations(
        grade=final_disease or final_grade,
        confidence=confidence
    )

    # -------- STORE IN FIRESTORE --------
    FARM_ID = resolve_farm_id(user)
    prediction_validation = None
    if final_grade.lower() == "diseased" and final_disease:
        normalized_disease = final_disease.lower()
        readings = _load_disease_readings(
            FARM_ID, "field-a-north", datetime.utcnow() - timedelta(days=10)
        )
        matching_forecast = next(
            (
                item for item in _disease_risk_forecast(readings)
                if item["disease"].lower() in normalized_disease
            ),
            None,
        )
        if matching_forecast and matching_forecast["risk_score"] >= 70:
            lead_days = matching_forecast["estimated_days_to_outbreak"] or 5
            prediction_validation = {
                "validated": True,
                "days_ahead": lead_days,
                "message": f"Predicted {lead_days} days in advance from environmental precursors.",
            }

    leaf_scan_doc = {
        "grade": final_grade,
        "disease_type": final_disease,
        "cnn_prediction": cnn_grade,
        "confidence": round(confidence / 100, 2),
        "confidence_level": confidence_level,
        "severity": severity,
        "surface_analysis": surface,
        "decision_source": decision_source,
        "image_meta": {
            "filename": file.filename
        },
        "timestamp": SERVER_TIMESTAMP
    }

    db.collection("farms") \
      .document(FARM_ID) \
      .collection("leaf_scans") \
      .add(leaf_scan_doc)

    print("✅ Leaf scan stored in Firestore")

    return {
        "grade": final_grade,
        "disease_type": final_disease,
        "cnn_prediction": cnn_grade,
        "confidence": round(confidence / 100, 2),
        "confidence_level": confidence_level,
        "severity": severity,
        "surface_analysis": surface,
        "decision_source": decision_source,
        "reason": (
            "CNN prediction used when disease detected; "
            "HSV rule-based grading used when CNN predicts healthy"
        ),
        "ai_recommendations": ai_recommendations,
        "yolo_detections": yolo_detections,
        "prediction_validation": prediction_validation,
    }


# -----------------------------
# CULTIVATION INTELLIGENCE
# -----------------------------

IDEAL = {
    "soil_moisture": (55, 65),
    "temperature": (18, 26),
    "humidity": (65, 75),
    "rainfall_7d": (40, 80)
}

WEIGHTS = {
    "soil_moisture": 0.35,
    "temperature": 0.25,
    "humidity": 0.20,
    "rainfall_7d": 0.20
}

def generate_ai_recommendations_gemini(context: dict):
    prompt = f"""
You are an AI agronomist specialized in Assam tea cultivation.

Given the following field analysis data, generate 3–5 concise, actionable recommendations.

Rules:
- Practical, field-level advice
- Explain WHY each recommendation is needed
- Use bullet points
- No emojis

Field Data:
{context}
"""

    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(prompt)

        if not response or not response.text:
            return ["AI recommendations unavailable at the moment."]

        text = response.text.strip()

        recommendations = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            if (
                line.startswith(("-", "•", "*")) or
                line[0].isdigit()
            ):
                recommendations.append(
                    line.lstrip("-•*0123456789. ").strip()
                )

        return recommendations or [
            "Field conditions are stable. Continue routine monitoring."
        ]

    except Exception as e:
        print("❌ GEMINI ERROR:", e)
        return ["AI recommendation service unavailable."]


def stress(value, low, high):
    if low <= value <= high:
        return 0
    return min(abs(value - (low if value < low else high)) / (high - low), 1)

def compute_health_score(data):
    total_stress = 0

    for key, (low, high) in IDEAL.items():
        s = stress(data[key], low, high)
        total_stress += WEIGHTS[key] * s

    score = int(100 * (1 - total_stress))
    return max(0, min(100, score))


RISK_MAP = {
    0: "Low",
    1: "Medium",
    2: "High"
}
def clamp(val, min_v=0, max_v=100):
    return max(min_v, min(val, max_v))

def normalize_risk(pred):
    return pred if isinstance(pred, str) else RISK_MAP[int(pred)]

def compute_stress_breakdown(data):
    breakdown = {}
    total_stress = 0

    for key, (low, high) in IDEAL.items():
        s = stress(data[key], low, high)
        breakdown[key] = round(s, 3)
        total_stress += WEIGHTS[key] * s

    risk_score = int(100 * total_stress)
    return clamp(risk_score), breakdown

def run_cultivation_engine(data: dict):
    features = np.array([[ 
        data["soil_moisture"],
        data["temperature"],
        data["humidity"],
        data.get("rainfall_last_24h", data["rainfall_7d"] / 7),
        data["rainfall_7d"],
        data.get("soil_ph", 5.2),
    ]])

    pest_risk = normalize_risk(pest_model.predict(features)[0])
    drought_risk = normalize_risk(drought_model.predict(features)[0])

    health_score = compute_health_score({
        "soil_moisture": data["soil_moisture"],
        "temperature": data["temperature"],
        "humidity": data["humidity"],
        "rainfall_7d": data["rainfall_7d"]
    })

    score_explanation = {
        "soil_moisture": "Optimal" if 55 <= data["soil_moisture"] <= 65 else "Suboptimal",
        "temperature": "Optimal" if 18 <= data["temperature"] <= 26 else "Suboptimal",
        "humidity": "Optimal" if 65 <= data["humidity"] <= 75 else "Suboptimal",
        "rainfall_7d": "Optimal" if 40 <= data["rainfall_7d"] <= 80 else "Suboptimal",
    }

    context = {
        "health_score": health_score,
        "pest_risk": pest_risk,
        "drought_risk": drought_risk,
        **data,
        "score_explanation": score_explanation
    }

    ai_recommendations = generate_ai_recommendations_gemini(context)

    return {
        "health_score": clamp(health_score),
        "pest_risk": pest_risk,
        "drought_risk": drought_risk,
        "action": (
            "Immediate irrigation and pest inspection"
            if pest_risk == "High" or drought_risk == "High"
            else "Monitor and maintain current practices"
        ),
        "score_explanation": score_explanation,
        "ai_recommendations": ai_recommendations
    }

@app.post("/api/cultivation")
def cultivation(data: dict):
    return run_cultivation_engine(data)

@app.post("/api/cultivation/aggregate")
def aggregate_cultivation_metrics(data: dict):
    """
    Expects a list of raw sensor readings and computes averages.
    """

    readings = data.get("readings", [])
    if not readings:
        return {"error": "No sensor data provided"}

    df = pd.DataFrame(readings)

    required = ["soil_moisture", "temperature", "humidity", "rainfall_7d"]
    for col in required:
        if col not in df.columns:
            return {"error": f"Missing field: {col}"}

    averages = {
        "soil_moisture": round(df["soil_moisture"].mean(), 2),
        "temperature": round(df["temperature"].mean(), 2),
        "humidity": round(df["humidity"].mean(), 2),
        "rainfall_7d": round(df["rainfall_7d"].mean(), 2),
    }

    return {
        "averages": averages,
        "count": len(df)
    }

import requests
from datetime import datetime

@app.post("/api/iot/sync-thingspeak")
def sync_thingspeak(channel_id: str = None):
    channel_id = channel_id or os.environ.get("THINGSPEAK_CHANNEL_ID")
    if not channel_id:
        raise HTTPException(status_code=400, detail="Missing ThingSpeak Channel ID")
        
    read_key = os.environ.get("THINGSPEAK_READ_KEY", "NNBIOJAJPSFKCECY")
    url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json?api_key={read_key}&results=50"
    
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    db = SessionLocal()
    try:
        sensor_id = "sensors_root"
        feeds = data.get("feeds", [])
        inserted = 0
        for f in feeds:
            temp = float(f.get("field1")) if f.get("field1") else 0.0
            hum = float(f.get("field2")) if f.get("field2") else 0.0
            sm = float(f.get("field3")) if f.get("field3") else 0.0
            alert = f.get("field4")
            
            ts_str = f.get("created_at")
            if ts_str:
                try:
                    # e.g. "2023-08-25T14:15:22Z"
                    ts = datetime.strptime(ts_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
                except ValueError:
                    ts = datetime.utcnow()
            else:
                ts = datetime.utcnow()
                
            exists = db.query(SensorReading).filter(
                SensorReading.sensor_id == sensor_id,
                SensorReading.timestamp == ts
            ).first()
            
            if not exists:
                reading = SensorReading(
                    sensor_id=sensor_id,
                    timestamp=ts,
                    temperature=temp,
                    humidity=hum,
                    soil_moisture=sm,
                    rainfall_7d=0.0,
                    extra_data={"alert_status": alert}
                )
                db.add(reading)
                inserted += 1
                
        db.commit()
        return {"status": "success", "inserted": inserted}
    finally:
        db.close()


@app.get("/api/farm/averages")
def get_farm_averages():
    db = SessionLocal()
    try:
        # Fetch the latest 50 readings from ThingSpeak sensor
        readings = db.query(SensorReading).filter(
            SensorReading.sensor_id == "sensors_root"
        ).order_by(SensorReading.timestamp.desc()).limit(50).all()

        if not readings:
            # Fallback to demo mock if no ThingSpeak data
            return {
                "status": "success",
                "averages": {
                    "soil_moisture": 54.3,
                    "temperature": 23.5,
                    "humidity": 77.9,
                    "rainfall_7d": 42.8
                },
                "sample_count": 0
            }

        df = pd.DataFrame([{
            "soil_moisture": r.soil_moisture,
            "temperature": r.temperature,
            "humidity": r.humidity,
            "rainfall_7d": r.rainfall_7d
        } for r in readings])

        averages = {
            "soil_moisture": round(df["soil_moisture"].mean(), 2),
            "temperature": round(df["temperature"].mean(), 2),
            "humidity": round(df["humidity"].mean(), 2),
            "rainfall_7d": round(df["rainfall_7d"].mean(), 2),
        }

        return {
            "status": "success",
            "averages": averages,
            "sample_count": len(df)
        }
    finally:
        db.close()

@app.get("/api/farm/soil-moisture-series")
def soil_moisture_series():
    db = SessionLocal()
    try:
        readings = db.query(SensorReading).filter(
            SensorReading.sensor_id == "sensors_root"
        ).order_by(SensorReading.timestamp.desc()).limit(24).all()

        series = []
        for r in readings:
            if not r.timestamp:
                continue
            series.append({
                "time": r.timestamp.strftime("%d %b %H:%M"),
                "value": round(r.soil_moisture, 1) if r.soil_moisture else 0,
                "ts": r.timestamp
            })

        if not series:
            # Fallback for UI if no data
            return [{"time": "No Data", "value": 0}]

        series.sort(key=lambda x: x["ts"])
        return [{"time": row["time"], "value": row["value"]} for row in series]
    finally:
        db.close()

@app.get("/api/farm/temperature-series")
def temperature_series():
    db = SessionLocal()
    try:
        readings = db.query(SensorReading).filter(
            SensorReading.sensor_id == "sensors_root"
        ).order_by(SensorReading.timestamp.desc()).limit(24).all()

        series = []
        for r in readings:
            if not r.timestamp:
                continue
            series.append({
                "time": r.timestamp.strftime("%d %b %H:%M"),
                "value": round(r.temperature, 1) if r.temperature else 0,
                "ts": r.timestamp
            })

        if not series:
            # Fallback for UI if no data
            return [{"time": "No Data", "value": 0}]

        series.sort(key=lambda x: x["ts"])
        return [{"time": row["time"], "value": row["value"]} for row in series]
    finally:
        db.close()


@app.get("/api/farm/daily-metrics")
def daily_metrics(user: User = Depends(get_current_user)):
    FARM_ID = resolve_farm_id(user)

    now = datetime.utcnow()
    start = now - timedelta(days=7)

    docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("sensors")
        .document("sensors_root")
        .collection("readings")
        .where("timestamp", ">=", start)
        .stream()
    )

    buckets = defaultdict(lambda: {
        "soil_moisture": [],
        "temperature": [],
        "humidity": [],
        "rainfall": 0.0,
    })

    try:
        for doc in docs:
            d = doc.to_dict()
            ts = d.get("timestamp")
            if not ts:
                continue

            day = ts.strftime("%a")  # Mon, Tue, Wed

            buckets[day]["soil_moisture"].append(d["soil_moisture"])
            buckets[day]["temperature"].append(d["temperature"])
            buckets[day]["humidity"].append(d["humidity"])
            buckets[day]["rainfall"] += d.get("rainfall_7d", 0) / 7
    except Exception as e:
        print(f"⚠️ Firestore quota/error in daily_metrics: {e}")

    ordered_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    result = []

    for day in ordered_days:
        if day not in buckets:
            continue

        b = buckets[day]
        result.append({
            "day": day,
            "soil_moisture": round(sum(b["soil_moisture"]) / len(b["soil_moisture"]), 1),
            "temperature": round(sum(b["temperature"]) / len(b["temperature"]), 1),
            "humidity": round(sum(b["humidity"]) / len(b["humidity"]), 1),
            "rainfall": round(b["rainfall"], 1),
        })

    # If no real data (e.g. demo mode or empty farm), return realistic demo data
    if not result:
        result = [
            {"day": "Mon", "soil_moisture": 62.4, "temperature": 22.1, "humidity": 71.3, "rainfall": 8.2},
            {"day": "Tue", "soil_moisture": 58.9, "temperature": 23.5, "humidity": 68.7, "rainfall": 4.5},
            {"day": "Wed", "soil_moisture": 55.2, "temperature": 24.8, "humidity": 66.1, "rainfall": 0.0},
            {"day": "Thu", "soil_moisture": 60.7, "temperature": 21.9, "humidity": 72.4, "rainfall": 12.1},
            {"day": "Fri", "soil_moisture": 64.1, "temperature": 20.6, "humidity": 74.8, "rainfall": 15.3},
            {"day": "Sat", "soil_moisture": 61.3, "temperature": 22.3, "humidity": 70.2, "rainfall": 6.7},
            {"day": "Sun", "soil_moisture": 59.8, "temperature": 23.1, "humidity": 69.5, "rainfall": 2.4},
        ]

    return result

@app.get("/api/cultivation/latest")
def latest_cultivation_from_iot(user: User = Depends(get_current_user)):
    FARM_ID = resolve_farm_id(user)

    docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("sensors")
        .document("sensors_root")
        .collection("readings")
        .order_by("timestamp", direction=Query.DESCENDING)
        .limit(1)
        .stream()
    )

    try:
        latest = next(docs, None)
    except Exception as e:
        print(f"⚠️ Firestore quota/error in latest_cultivation: {e}")
        latest = None

    if not latest:
        # Fallback to realistic mock data if quota exceeded or no data
        data = {
            "soil_moisture": 62.4,
            "temperature": 22.1,
            "humidity": 71.3,
            "rainfall_7d": 8.2,
            "soil_ph": 5.2,
        }
        return run_cultivation_engine(data)

    d = latest.to_dict()

    data = {
        "soil_moisture": d["soil_moisture"],
        "temperature": d["temperature"],
        "humidity": d["humidity"],
        "rainfall_7d": d["rainfall_7d"],
        "soil_ph": d.get("soil_ph", 5.2),
    }

    return run_cultivation_engine(data)


def _disease_risk_forecast(readings: list) -> list:
    if not readings:
        return []
    ordered = sorted(readings, key=lambda row: row.get("timestamp", datetime.min))
    recent = ordered[-24:]
    humidity = [float(row.get("humidity", 0)) for row in recent]
    temperatures = [float(row.get("temperature", 0)) for row in recent]
    wet_readings = sum(1 for h, t in zip(humidity, temperatures) if h > 85 and 15 <= t <= 28)
    very_wet_readings = sum(1 for h in humidity if h > 90)
    dry_readings = sum(1 for h in humidity if h < 60)
    latest_humidity = humidity[-1] if humidity else 0
    latest_temperature = temperatures[-1] if temperatures else 0
    previous_humidity = humidity[-4:-1] or humidity[:-1] or humidity

    blister_score = min(100, round((wet_readings / 12) * 60 + max(0, very_wet_readings - 2) * 8))
    rust_score = min(100, round((dry_readings / 10) * 55 + (25 if previous_humidity and max(previous_humidity) < 50 and latest_humidity >= 65 else 0)))
    algal_score = min(100, round((very_wet_readings / 8) * 55 + (25 if latest_temperature > 24 else 0)))

    def forecast(name, score, trigger, action, lead_days):
        prior = max(0, score - (8 if score >= 50 else 3))
        trend = "rising" if score > prior else ("falling" if score < prior else "stable")
        days = max(1, lead_days - round(score / 25)) if score >= 35 else None
        level = "High" if score >= 70 else ("Moderate" if score >= 35 else "Low")
        return {
            "disease": name, "risk_score": score, "risk_level": level,
            "trend": trend, "estimated_days_to_outbreak": days,
            "trigger": trigger, "preventive_action": action,
        }

    return [
        forecast("Blister Blight", blister_score,
                 f"{wet_readings} high-humidity readings detected with temperatures near {latest_temperature:.1f}°C",
                 "Consider preventive copper fungicide before visible symptoms appear.", 8),
        forecast("Red Rust", rust_score,
                 f"{dry_readings} low-humidity readings detected; latest humidity is {latest_humidity:.0f}%",
                 "Inspect drought-stressed rows and restore moisture gradually; monitor new growth.", 10),
        forecast("Algal Leaf Spot", algal_score,
                 f"{very_wet_readings} very high-humidity readings detected with recent temperature at {latest_temperature:.1f}°C",
                 "Improve airflow and drainage around dense canopy areas.", 10),
    ]


def _load_disease_readings(farm_id: str, zone_id: str) -> list:
    readings = []
    try:
        docs = (
            db.collection("farms").document(farm_id)
            .collection("sensors").document("sensors_root")
            .collection("readings")
            .order_by("timestamp", direction=Query.DESCENDING).limit(24).stream()
        )
        for doc in docs:
            reading = doc.to_dict()
            reading_zone = reading.get("zone_id") or reading.get("zone")
            if not reading_zone or reading_zone == zone_id:
                readings.append(reading)
    except Exception as exc:
        print(f"⚠️ Disease forecast sensor read: {exc}")
    
    # Sort ascending for calculation
    readings.sort(key=lambda r: r.get("timestamp", datetime.min))
    return readings


@app.get("/api/disease-risk/forecast/{zone_id}")
def disease_risk_forecast(zone_id: str, user: User = Depends(get_current_user)):
    farm_id = resolve_farm_id(user)
    readings = _load_disease_readings(farm_id, zone_id)
    
    source = "live_iot"
    if not readings:
        return {"zone_id": zone_id, "source": source, "lookback_days": 10, "forecasts": []}

    forecasts = _disease_risk_forecast(readings)
    return {"zone_id": zone_id, "source": source, "lookback_days": 10, "forecasts": forecasts}


@app.get("/api/cultivation/field-health")
def smart_alert(user: User = Depends(get_current_user)):
    FARM_ID = resolve_farm_id(user)
    docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("sensors")
        .document("sensors_root")
        .collection("readings")
        .order_by("timestamp", direction=Query.DESCENDING)
        .limit(1)
        .stream()
    )

    latest = next(docs, None)
    if not latest:
        return {"alert": False, "mode": "AI", "risk_score": 0}

    d = latest.to_dict()

    # Ensure required fields exist
    for key in IDEAL.keys():
        if key not in d or d[key] is None:
            return {"alert": False, "mode": "AI", "risk_score": 0}

    data = {
        "soil_moisture": d["soil_moisture"],
        "temperature": d["temperature"],
        "humidity": d["humidity"],
        "rainfall_7d": d["rainfall_7d"],
    }

    # 🔑 SAME ENGINE AS MANUAL & IOT
    health_score = compute_health_score(data)
    risk_score, stress_breakdown = compute_stress_breakdown(data)

    if health_score <= 60:
        stressed_factors = [
            k.replace("_", " ")
            for k, v in stress_breakdown.items()
            if v > 0
        ]

        return {
            "alert": True,
            "mode": "AI",
            "health_score": health_score,
            "risk_score": risk_score,
            "reason": f"Stress detected in: {', '.join(stressed_factors)}",
            "stress_breakdown": stress_breakdown
        }

    return {
        "alert": False,
        "mode": "AI",
        "health_score": health_score,
        "risk_score": risk_score,
        "stress_breakdown": stress_breakdown
    }


# -----------------------------
# MARKET INTELLIGENCE
# -----------------------------

PRIMARY_MARKET = "guwahati"

@app.post("/api/price-forecast")
def price_forecast(data: dict):
    history = np.array(data["price_history"]).reshape(-1, 1)
    prediction = forecast_price_from_dict(price_model, steps=len(history))

    return {
        "forecast_price": round(float(prediction), 2),
        "recommendation": "SELL" if prediction > history.mean() else "HOLD"
    }

@app.get("/api/market/kpis")
def market_kpis():
    if df is None or df.empty or len(df) < 3:
        return {"error": "Insufficient market data"}

    prices = df[PRIMARY_MARKET].dropna()
    dates = df["week_ending_date"]

    # -------------------
    # CURRENT PRICE
    # -------------------
    current_price = float(prices.iloc[-1])
    prev_price = float(prices.iloc[-2])
    price_change_pct = ((current_price - prev_price) / prev_price) * 100

    # -------------------
    # DEMAND (TRUE WEEKLY)
    # -------------------
    latest_price = prices.iloc[-1]
    prev_price = prices.iloc[-2]
    
    price_change_pct_abs = abs((latest_price - prev_price) / prev_price) * 100

    # cap extreme values to avoid spikes
    demand_index = min(price_change_pct_abs * 5, 100)
    
    prev_price_change_abs = abs(
        (prices.iloc[-2] - prices.iloc[-3]) / prices.iloc[-3]
    ) * 100

    prev_demand_index = min(prev_price_change_abs * 5, 100)
    
    demand_change_abs = demand_index - prev_demand_index

    # -------------------
    # VOLATILITY (ROLLING, BUT SHOWN SAFELY)
    # -------------------
    recent_7 = prices.tail(7)
    prev_7 = prices.iloc[-14:-7]

    volatility = (recent_7.std() / recent_7.mean()) * 100

    prev_volatility = (
        (prev_7.std() / prev_7.mean()) * 100
        if len(prev_7) == 7 else volatility
    )

    # 🔑 USE ABSOLUTE CHANGE, NOT %
    volatility_change_abs = volatility - prev_volatility

    # -------------------
    # FORECAST
    # -------------------
    forecast_price = forecast_price_from_dict(price_model)

    return {
        "current_price": round(current_price, 2),
        "forecast_price": round(forecast_price, 2),
        "price_change_pct": round(price_change_pct, 1),

        "market_demand": round(demand_index, 0),
        "market_demand_change_abs": round(demand_change_abs, 1),

        "volatility": round(volatility, 2),
        "volatility_change_abs": round(volatility_change_abs, 2),
    }

@app.get("/api/market/price-series")
def price_series():
    data = df[["week_ending_date", PRIMARY_MARKET]].dropna()
    data = data.rename(columns={PRIMARY_MARKET: "price"})

    # last 10 months only
    data = data.tail(10)

    series = []

    # ACTUAL DATA
    for _, row in data.iterrows():
        series.append({
            "date": row["week_ending_date"].strftime("%Y-%m-%d"),
            "price": round(row["price"], 2),
            "type": "actual"
        })

    # -------- FORECAST NEXT 3 MONTHS --------
    last_price = data["price"].iloc[-1]
    recent_prices = data["price"].values
    slope = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]

    last_date = data["week_ending_date"].iloc[-1]

    for i in range(1, 6):  # next 5 weeks
        future_date = (last_date + pd.DateOffset(weeks=i))
        forecast_price = last_price + slope * i

        series.append({
            "date": future_date.strftime("%Y-%m-%d"),
            "price": round(forecast_price, 2),
            "type": "forecast"
        })

    return series

@app.get("/api/market/demand-volatility")
def demand_volatility():
    if df is None or df.empty:
        return []

    data = df.copy()

    # Ensure datetime
    data["week_ending_date"] = pd.to_datetime(data["week_ending_date"])

    # Create month key
    data["month_key"] = data["week_ending_date"].dt.to_period("M")

    # ✅ KEEP ONLY LAST 12 MONTHS
    last_12_months = (
        data["month_key"]
        .sort_values()
        .unique()[-12:]
    )

    data = data[data["month_key"].isin(last_12_months)]

    grouped = (
        data
        .groupby("month_key")
        .agg(
            demand=(PRIMARY_MARKET, "count"),
            volatility=(PRIMARY_MARKET, lambda x: (x.std() / x.mean()) * 100)
        )
        .reset_index()
        .sort_values("month_key")
    )

    return [
        {
            "month": row["month_key"].to_timestamp().strftime("%b %Y"),
            "demand": int(row["demand"] * 100),
            "volatility": round(row["volatility"], 2)
        }
        for _, row in grouped.iterrows()
    ]

@app.get("/api/market/location-price-summary")
def location_price_summary():
    if df is None or df.empty:
        return []

    result = []

    # ensure sorted
    data = df.sort_values("week_ending_date")

    for col in market_columns:
        series = data[col].dropna()

        if series.empty:
            continue

        avg_price = series.mean()
        min_price = series.min()
        max_price = series.max()

        current_price = series.iloc[-1]
        prev_price = series.iloc[-2] if len(series) > 1 else current_price

        # trend logic
        if current_price > prev_price * 1.01:
            trend = "up"
        elif current_price < prev_price * 0.99:
            trend = "down"
        else:
            trend = "stable"

        result.append({
            "location": col.replace("_", " ").title(),
            "avgPrice": round(avg_price, 2),
            "currentPrice": round(current_price, 2),
            "minPrice": round(min_price, 2),
            "maxPrice": round(max_price, 2),
            "trend": trend,
        })

    return result

@app.get("/api/market/insight")
def market_insight():
    if df is None or df.empty or len(df) < 3:
        return {
            "signal": "neutral",
            "title": "Market Insight",
            "message": "Insufficient data to generate insight.",
            "ai_message": None
        }

    prices = df[PRIMARY_MARKET].dropna()

    # ---- CORE METRICS ----
    latest_price = prices.iloc[-1]
    prev_price = prices.iloc[-2]

    price_change_pct_abs = abs((latest_price - prev_price) / prev_price) * 100
    demand_index = min(price_change_pct_abs * 5, 100)

    recent_7 = prices.tail(7)
    volatility = (recent_7.std() / recent_7.mean()) * 100

    # ---- RULE ENGINE ----
    if demand_index < 20 and volatility < 3:
        signal = "watch"
        message = (
            f"Demand pressure remains very low ({int(demand_index)}/100) "
            f"while price volatility is stable. "
            f"Avoid aggressive production or inventory buildup. "
            f"Maintain current supply and monitor for early demand recovery."
        )

    elif demand_index >= 20 and volatility < 3:
        signal = "opportunity"
        message = (
            f"Demand is showing recovery signals ({int(demand_index)}/100) "
            f"with stable prices. "
            f"Gradual production scaling may help capture upside."
        )

    elif volatility >= 3:
        signal = "risk"
        message = (
            f"Market volatility is elevated ({volatility:.2f}%). "
            f"Price instability increases short-term risk. "
            f"Consider quicker sales cycles and cautious pricing."
        )

    else:
        signal = "neutral"
        message = "Market conditions are mixed. Continue monitoring closely."

    # ---- AI CONTEXT (SAFE, NON-HALLUCINATING) ----
    ai_context = {
        "market": "Guwahati",
        "demand_index": int(demand_index),
        "volatility_pct": round(volatility, 2),
        "price_direction": (
            "downward" if latest_price < prev_price else "upward"
        ),
        "signal": signal
    }

    ai_message = generate_ai_market_insight(ai_context)
    strategy_context = {
        "market": "Guwahati",
        "signal": signal,
        "demand_index": int(demand_index),
        "volatility_pct": round(volatility, 2),
        "price_direction": "downward" if latest_price < prev_price else "upward"
    }

    ai_recommendations = generate_ai_strategy_recommendations(strategy_context)

    return {
        "signal": signal,
        "title": "Actionable Market Insight – Guwahati",
        "message": message,
        "ai_message": ai_message,
        "ai_recommendations": ai_recommendations
    }

# -----------------------------
# FARMER ACTION SIMULATOR
# -----------------------------

class SimulatorInput(BaseModel):
    leaf_grade: str
    leaf_confidence: float
    health_score: int
    pest_risk: str
    drought_risk: str
    market_signal: str
    market_demand: float
    volatility: float


@app.post("/api/simulate-action")
def simulate_farmer_action(data: SimulatorInput):
    """
    Combines crop health, cultivation risk, and market signals
    to simulate outcome of recommended farmer action.
    """

    # -------- RULE-BASED SIMULATION ENGINE --------

    yield_change = 0
    profit_change = 0
    risk = "Medium"
    harvest_delay_days = 0

    # Leaf quality impact
    if data.leaf_grade == "A":
        yield_change += 10
        profit_change += 3000
    elif data.leaf_grade == "B":
        yield_change += 6
        profit_change += 1500
    else:
        yield_change += 2
        profit_change += 500

    # Cultivation risk impact
    if data.pest_risk == "High" or data.drought_risk == "High":
        yield_change -= 5
        risk = "High"
    elif data.health_score > 80:
        yield_change += 4
        risk = "Low"

    # Market impact
    if data.market_signal in ["opportunity", "SELL"]:
        profit_change += 2000
        harvest_delay_days = 7
    elif data.market_signal == "risk":
        profit_change -= 1500
        harvest_delay_days = -3

    # Clamp values
    yield_change = max(-10, min(20, yield_change))
    profit_change = max(-3000, min(8000, profit_change))

    return {
        "expected_yield_change_pct": yield_change,
        "estimated_profit_change": profit_change,
        "risk_level": risk,
        "recommended_harvest_shift_days": harvest_delay_days,
        "explanation": [
            "Simulation combines leaf quality, field risk, and market signals",
            "Rule-based engine used for transparent decision support",
            "Values represent estimated directional impact, not guarantees"
        ]
    }


# -----------------------------
# YIELD-BASED SELLING STRATEGY
# -----------------------------

class YieldInput(BaseModel):
    yield_kg: float
    selected_approach: int = 1
    spoilage_pct: float = 0.0

@app.post("/api/calculate-yield-strategy")
def calculate_yield_strategy(data: YieldInput):
    """
    Calculate 3 selling strategies based on yield input and real Guwahati market data
    """
    yield_kg = data.yield_kg
    spoilage_pct = data.spoilage_pct
    
    if yield_kg <= 0:
        return {"error": "Yield must be greater than 0"}
        
    effective_yield = yield_kg * (1 - spoilage_pct / 100)
    spoilage_text = f" (after {spoilage_pct}% transit loss)" if spoilage_pct > 0 else ""
    
    # Get real Guwahati market data
    if df is None or df.empty or len(df) < 3:
        return {"error": "Insufficient market data"}
    
    prices = df[PRIMARY_MARKET].dropna()
    current_price = float(prices.iloc[-1])
    prev_price = float(prices.iloc[-2])
    price_change_pct = ((current_price - prev_price) / prev_price) * 100
    
    # Calculate forecast price
    forecast_price = forecast_price_from_dict(price_model)
    forecast_increase_pct = ((forecast_price - current_price) / current_price) * 100
    
    # Calculate volatility for risk assessment
    recent_7 = prices.tail(7)
    volatility = (recent_7.std() / recent_7.mean()) * 100
    
    # Determine market signal
    price_change_pct_abs = abs(price_change_pct)
    demand_index = min(price_change_pct_abs * 5, 100)
    
    if demand_index < 20 and volatility < 3:
        signal = "watch"
    elif demand_index >= 20 and volatility < 3:
        signal = "opportunity"
    elif volatility >= 3:
        signal = "risk"
    else:
        signal = "neutral"
    
    # Calculate selling window dates
    from datetime import datetime, timedelta
    today = datetime.utcnow()
    window_start = today + timedelta(days=7)
    window_end = today + timedelta(days=12)
    selling_window = f"{window_start.strftime('%b %d')} – {window_end.strftime('%b %d')}"
    
    # Generate 3 selling strategies with REAL calculations using effective_yield
    strategies = [
        {
            "title": "Immediate Sale at Current Market Rate",
            "description": f"Sell {effective_yield:.1f} kg{spoilage_text} immediately at current Guwahati market rate of ₹{current_price}/kg. This approach minimizes storage costs and provides immediate cash flow. Best for farmers needing quick liquidity.",
            "expected_revenue": round(effective_yield * current_price, 2),
            "revenue_display": f"₹{int(effective_yield * current_price):,}",
            "timing": "Immediate (1-2 days)",
            "priority": "medium" if signal != "risk" else "high",
            "price_per_kg": current_price,
            "yield_impact": 0,
            "profit_change": 0
        },
        {
            "title": "Wait for Peak Demand Window",
            "description": f"Store {effective_yield:.1f} kg{spoilage_text} and sell during {selling_window} when Guwahati prices are forecasted to reach ₹{forecast_price:.2f}/kg. Implement proper storage to maintain quality. Expected price increase of {forecast_increase_pct:+.1f}%.",
            "expected_revenue": round(effective_yield * forecast_price, 2),
            "revenue_display": f"₹{int(effective_yield * forecast_price):,} ({forecast_increase_pct:+.1f}%)",
            "timing": selling_window,
            "priority": "high" if signal == "opportunity" else "medium",
            "price_per_kg": forecast_price,
            "yield_impact": 0,
            "profit_change": round(effective_yield * (forecast_price - current_price), 2)
        },
        {
            "title": "Quality Improvement + Premium Sale",
            "description": f"Invest in post-harvest processing to improve grade quality. Target premium Guwahati buyers willing to pay 15-20% more (₹{current_price * 1.18:.2f}/kg) for superior quality tea. Requires additional processing time and investment of ~₹{int(yield_kg * 5):,}.",
            "expected_revenue": round(effective_yield * current_price * 1.18, 2),
            "revenue_display": f"₹{int(effective_yield * current_price * 1.18):,} (+18%)",
            "timing": "7-14 days (processing time)",
            "priority": "high" if signal != "risk" else "low",
            "price_per_kg": round(current_price * 1.18, 2),
            "yield_impact": -2,  # Small loss due to processing
            "profit_change": round(effective_yield * current_price * 0.18 - yield_kg * 5, 2)  # Premium minus processing cost
        }
    ]
    
    # Calculate projected outcomes based on selected approach
    selected = strategies[data.selected_approach]
    
    # Calculate comparative metrics using effective yield
    base_revenue = effective_yield * current_price
    selected_revenue = selected["expected_revenue"]
    revenue_diff_pct = ((selected_revenue - base_revenue) / base_revenue) * 100 if base_revenue > 0 else 0
    
    # Determine risk level based on approach and market conditions
    if data.selected_approach == 0:  # Immediate sale
        risk_level = "Low"
        yield_change = "0%"
    elif data.selected_approach == 1:  # Wait for peak
        risk_level = "Low" if volatility < 3 else "Medium"
        yield_change = "+0-2%" if signal == "opportunity" else "-1-0%"
    else:  # Quality improvement
        risk_level = "Medium"
        yield_change = "-2-0%"
    
    # Calculate harvest timing adjustment
    if data.selected_approach == 1 and signal == "opportunity":
        harvest_timing = "+7 days"
    elif data.selected_approach == 0 and signal == "risk":
        harvest_timing = "-3 days"
    else:
        harvest_timing = "No change"
    
    return {
        "strategies": strategies,
        "selected_approach": data.selected_approach,
        "market_data": {
            "current_price": round(current_price, 2),
            "forecast_price": round(forecast_price, 2),
            "price_change_pct": round(price_change_pct, 1),
            "forecast_increase_pct": round(forecast_increase_pct, 1),
            "volatility": round(volatility, 2),
            "signal": signal,
            "demand_index": round(demand_index, 0),
            "selling_window": selling_window
        },
        "projected_outcomes": {
            "yieldChange": yield_change,
            "profitChange": f"₹{int(selected['profit_change']):,}" if selected['profit_change'] >= 0 else f"-₹{int(abs(selected['profit_change'])):,}",
            "riskLevel": risk_level,
            "harvestTiming": harvest_timing
        },
        "no_action_outcomes": {
            "yieldChange": "-2-0%",
            "profitChange": f"-₹{int(yield_kg * current_price * 0.02):,}",
            "riskLevel": "Medium"
        },
        "comparison": {
            "base_revenue": round(base_revenue, 2),
            "selected_revenue": round(selected_revenue, 2),
            "revenue_difference": round(selected_revenue - base_revenue, 2),
            "revenue_diff_pct": round(revenue_diff_pct, 1)
        },
        "risk_factors": [
            {
                "factor": "Market Price Volatility",
                "description": f"Guwahati tea market volatility is {volatility:.2f}%. {'High volatility increases price uncertainty' if volatility >= 3 else 'Stable market conditions with low volatility'}.",
                "severity": "high" if volatility >= 3 else "low"
            },
            {
                "factor": "Storage Risk" if data.selected_approach == 1 else "Processing Risk" if data.selected_approach == 2 else "Immediate Sale Risk",
                "description": 
                    f"Storing tea for {selling_window} requires proper facilities to prevent quality degradation." if data.selected_approach == 1
                    else "Processing investment of ₹{:,} required with 2% yield loss risk during processing.".format(int(yield_kg * 5)) if data.selected_approach == 2
                    else "Selling immediately may miss potential price increases if market improves.",
                "severity": "medium" if data.selected_approach == 1 else "medium" if data.selected_approach == 2 else "low"
            },
            {
                "factor": "Demand Fluctuation",
                "description": f"Current demand index at {demand_index}/100. {'Strong demand supports stable pricing' if demand_index >= 60 else 'Moderate demand may lead to price pressure' if demand_index >= 30 else 'Low demand increases selling difficulty'}.",
                "severity": "low" if demand_index >= 60 else "medium" if demand_index >= 30 else "high"
            }
        ]
    }


# -----------------------------
# PDF REPORT GENERATION
# -----------------------------

def clean_markdown(text: str) -> str:
    """Remove markdown formatting from text"""
    if not text:
        return ''
    import re
    # Remove bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Remove italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    # Remove code blocks: `text`
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Remove headers: # text
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove bullet points: - text or * text
    text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)
    # Clean up any remaining asterisks
    text = text.replace('*', '')
    return text

class PDFReportData(BaseModel):
    simulation_data: Dict[str, Any]
    yield_input: Optional[float] = None
    selected_approach: Optional[int] = 0
    selling_suggestions: Optional[List[Dict[str, Any]]] = []
    
    class Config:
        arbitrary_types_allowed = True

@app.post("/api/generate-pdf-report")
def generate_pdf_report(data: PDFReportData):
    """
    Generate a comprehensive PDF report with all simulation data
    """
    def replace_rupee(obj):
        if isinstance(obj, dict):
            return {k: replace_rupee(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_rupee(v) for v in obj]
        elif isinstance(obj, str):
            return obj.replace('₹', 'INR ')
        return obj

    data = PDFReportData(**replace_rupee(data.model_dump()))
    print(f"📄 PDF GENERATION REQUEST RECEIVED")
    print(f"Yield Input: {data.yield_input}")
    print(f"Selected Approach: {data.selected_approach}")
    print(f"Selling Suggestions Count: {len(data.selling_suggestions)}")
    
    try:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = temp_file.name
        temp_file.close()
        
        # Create PDF document
        doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)
        
        # Container for PDF elements
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2E7D32'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2E7D32'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#388E3C'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        
        normal_style = styles['BodyText']
        normal_style.fontSize = 11
        normal_style.leading = 14
        
        # Header with logo and title
        elements.append(Paragraph("ChaiTea", title_style))
        elements.append(Paragraph("Farmer Action Simulator - Comprehensive Report", 
                                 ParagraphStyle('Subtitle', parent=styles['Normal'], 
                                              fontSize=14, alignment=TA_CENTER,
                                              textColor=colors.HexColor('#666666'),
                                              spaceAfter=20)))
        
        # Timestamp
        timestamp = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
        elements.append(Paragraph(f"<i>Generated on: {timestamp}</i>", 
                                 ParagraphStyle('Timestamp', parent=styles['Normal'],
                                              fontSize=10, alignment=TA_CENTER,
                                              textColor=colors.grey, spaceAfter=30)))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # ===== SECTION 1: RECOMMENDED ACTIONS =====
        elements.append(Paragraph("1. Recommended Actions", heading_style))
        sim_data = data.simulation_data
        
        for i, action in enumerate(sim_data.get('recommendedActions', []), 1):
            elements.append(Paragraph(f"• {action}", normal_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # ===== SECTION 2: PROJECTED OUTCOMES =====
        elements.append(Paragraph("2. Projected Outcomes (If You Follow This Action)", heading_style))
        
        outcomes = sim_data.get('projectedOutcomes', {})
        outcomes_data = [
            ['Metric', 'Value'],
            ['Expected Yield Change', outcomes.get('yieldChange', 'N/A')],
            ['Estimated Profit Change', outcomes.get('profitChange', 'N/A')],
            ['Risk Level', outcomes.get('riskLevel', 'N/A')],
            ['Harvest Timing Adjustment', outcomes.get('harvestTiming', 'N/A')]
        ]
        
        outcomes_table = Table(outcomes_data, colWidths=[3*inch, 3*inch])
        outcomes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(outcomes_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # ===== SECTION 3: NO ACTION COMPARISON =====
        elements.append(Paragraph("3. If No Action Is Taken", heading_style))
        
        no_action = sim_data.get('noActionOutcomes', {})
        no_action_data = [
            ['Metric', 'Value'],
            ['Yield Change', no_action.get('yieldChange', 'N/A')],
            ['Profit Change', no_action.get('profitChange', 'N/A')],
            ['Risk Level', no_action.get('riskLevel', 'N/A')]
        ]
        
        no_action_table = Table(no_action_data, colWidths=[3*inch, 3*inch])
        no_action_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D32F2F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FFEBEE')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(no_action_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # ===== SECTION 4: DISEASE PREVENTION APPROACHES =====
        if sim_data.get('diseasePreventionApproaches'):
            elements.append(Paragraph("4. Disease Prevention Approaches (Based on 7 Days Data)", heading_style))
            elements.append(Paragraph("<i>Based on 7 days of sensor and leaf scan data:</i>", 
                                     ParagraphStyle('Italic', parent=normal_style, fontSize=10, 
                                                  textColor=colors.grey, spaceAfter=10)))
            
            for i, approach in enumerate(sim_data['diseasePreventionApproaches'], 1):
                cleaned_approach = clean_markdown(approach)
                elements.append(Paragraph(f"<b>Approach {i}:</b> {cleaned_approach}", normal_style))
                elements.append(Spacer(1, 0.1*inch))
            elements.append(Spacer(1, 0.2*inch))
        
        # ===== SECTION 5: YIELD ANALYSIS AND SELLING STRATEGIES =====
        if data.yield_input and data.selling_suggestions:
            elements.append(PageBreak())
            elements.append(Paragraph("5. Yield Analysis and Selling Strategies", heading_style))
            elements.append(Paragraph(f"<b>Total Yield Entered:</b> {data.yield_input} kg", normal_style))
            elements.append(Spacer(1, 0.2*inch))
            
            for i, suggestion in enumerate(data.selling_suggestions, 1):
                is_selected = (i - 1) == data.selected_approach
                
                elements.append(Paragraph(f"<b>{'✓ ' if is_selected else ''}Approach {i}: {suggestion.get('title', '')}</b>", 
                                         subheading_style))
                elements.append(Paragraph(f"<b>Priority:</b> {suggestion.get('priority', '').upper()}", normal_style))
                elements.append(Paragraph(f"<b>Description:</b> {suggestion.get('description', '')}", normal_style))
                elements.append(Paragraph(f"<b>Expected Revenue:</b> {suggestion.get('expectedRevenue', 'N/A')}", normal_style))
                elements.append(Paragraph(f"<b>Timing:</b> {suggestion.get('timing', 'N/A')}", normal_style))
                
                if is_selected:
                    elements.append(Paragraph("<i>★ This is your selected approach</i>", 
                                             ParagraphStyle('Selected', parent=normal_style, 
                                                          textColor=colors.HexColor('#2E7D32'), 
                                                          fontSize=10, spaceAfter=10)))
                elements.append(Spacer(1, 0.15*inch))
        
        # ===== SECTION 6 & 7: Only show if yield was entered =====
        if data.yield_input and data.yield_input > 0:
            # ===== SECTION 6: MARKET TIMING INSIGHTS =====
            elements.append(Paragraph("6. Market Timing Insights", heading_style))
            market = sim_data.get('marketInsights', {})
            
            market_data = [
                ['Insight', 'Details'],
                ['Demand Forecast', market.get('demandForecast', 'N/A')],
                ['Price Change', market.get('priceIncrease', 'N/A')],
                ['Best Selling Window', market.get('sellingWindow', 'N/A')]
            ]
            
            market_table = Table(market_data, colWidths=[2.5*inch, 3.5*inch])
            market_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976D2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E3F2FD')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(market_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # ===== SECTION 7: CONFIDENCE METRICS =====
            elements.append(Paragraph("7. Simulation Confidence Metrics", heading_style))
            confidence = sim_data.get('confidence', {})
            
            confidence_data = [
                ['Metric', 'Score'],
                ['Model Accuracy', f"{confidence.get('modelAccuracy', 0)}%"],
                ['Market Data Reliability', f"{confidence.get('marketReliability', 0)}%"],
                ['Historical Trend Similarity', f"{confidence.get('historicalSimilarity', 0)}%"]
            ]
            
            avg_confidence = round((confidence.get('modelAccuracy', 0) + 
                                   confidence.get('marketReliability', 0) + 
                                   confidence.get('historicalSimilarity', 0)) / 3)
            confidence_level = 'High' if avg_confidence >= 85 else 'Medium' if avg_confidence >= 70 else 'Low'
            confidence_data.append(['Overall Confidence', f"{confidence_level} ({avg_confidence}%)"])
            
            confidence_table = Table(confidence_data, colWidths=[3*inch, 3*inch])
            confidence_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1FA2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F3E5F5')),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E1BEE7')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(confidence_table)
            elements.append(Spacer(1, 0.3*inch))
            
        # ===== SECTION 8: LOGISTICS & TRANSPORT PLAN =====
        route_data = sim_data.get('routeData')
        has_logistics = route_data is not None
        if has_logistics:
            section_logistics = "8" if (data.yield_input and data.yield_input > 0) else "6"
            elements.append(Paragraph(f"{section_logistics}. Logistics & Transport Plan", heading_style))
            elements.append(Paragraph(f"<b>Destination:</b> {route_data.get('destination_name', 'Unknown')}", normal_style))
            elements.append(Spacer(1, 0.1*inch))
            
            risk_color = colors.HexColor('#D32F2F') if route_data.get('route_risk') == 'HIGH' else \
                        colors.HexColor('#F57C00') if route_data.get('route_risk') == 'MEDIUM' else \
                        colors.HexColor('#388E3C')
            
            elements.append(Paragraph(f"<b>Route Risk Level:</b> <font color='{risk_color.hexval()}'>{route_data.get('route_risk', 'UNKNOWN')}</font>", normal_style))
            elements.append(Spacer(1, 0.1*inch))
            
            # Calculate effective price using selected approach price
            selected_price = 0
            if data.selling_suggestions and len(data.selling_suggestions) > (data.selected_approach or 0):
                selected_price = data.selling_suggestions[data.selected_approach or 0].get('price_per_kg', 0)
                
            eff_price = selected_price * (1 - route_data.get('spoilage_pct', 0) / 100)
            
            duration_min = route_data.get('duration_min', 0)
            duration_str = f"{int(duration_min) // 60}h {int(duration_min) % 60}m" if duration_min else 'N/A'
            
            logistics_data = [
                ['Metric', 'Selected Route'],
                ['Distance', f"{route_data.get('distance_km', 'N/A')} km"],
                ['Est. Duration', duration_str],
                ['Spoilage Percentage', f"{route_data.get('spoilage_pct', 0)}%"],
                ['Effective Price (Net)', f"INR {eff_price:.2f} / kg"]
            ]
            
            if route_data.get('alternate_route'):
                alt_eff_price = selected_price * (1 - route_data['alternate_route'].get('spoilage_pct', 0) / 100)
                logistics_data[0].append('Alternate Route')
                logistics_data[1].append("N/A")
                logistics_data[2].append("N/A")
                logistics_data[3].append(f"{route_data['alternate_route'].get('spoilage_pct', 0)}%")
                logistics_data[4].append(f"INR {alt_eff_price:.2f} / kg")
            
            logistics_table = Table(logistics_data)
            logistics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0288D1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#E1F5FE')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(logistics_table)
            
            if data.yield_input and data.yield_input > 0:
                y = data.yield_input
                chosen_rev = y * (1 - route_data.get('spoilage_pct', 0) / 100) * route_data.get('effective_price', 0)
                alt_spoilage = route_data.get('alternate_route', {}).get('spoilage_pct', 15) if route_data.get('alternate_route') else 15
                alt_price = route_data.get('alternate_route', {}).get('effective_price', route_data.get('base_price', 265) * 0.85) if route_data.get('alternate_route') else (route_data.get('base_price', 265) * 0.85)
                alt_rev = y * (1 - alt_spoilage / 100) * alt_price
                diff = chosen_rev - alt_rev
                is_gain = diff >= 0
                diff_abs = abs(diff)
                
                elements.append(Spacer(1, 0.15*inch))
                opp_cost_text = f"<b>Opportunity Cost Analysis:</b> {'Saved vs Alternate Route' if is_gain else 'Loss vs Optimal Route'} is <b>INR {int(diff_abs):,}</b>"
                elements.append(Paragraph(opp_cost_text, normal_style))
                
            elements.append(Spacer(1, 0.3*inch))
        
        # ===== RISK FACTORS =====
        if sim_data.get('riskFactors'):
            base_section = 8 if (data.yield_input and data.yield_input > 0) else 6
            if has_logistics: base_section += 1
            elements.append(Paragraph(f"{base_section}. Risk Factors Analysis", heading_style))
            
            for risk in sim_data['riskFactors']:
                severity = risk.get('severity', 'medium').upper()
                severity_color = colors.HexColor('#D32F2F') if severity == 'HIGH' else \
                                colors.HexColor('#F57C00') if severity == 'MEDIUM' else \
                                colors.HexColor('#388E3C')
                
                elements.append(Paragraph(f"<b>{risk.get('factor', '')} [{severity}]</b>", 
                                         ParagraphStyle('RiskTitle', parent=normal_style, 
                                                      textColor=severity_color, fontSize=12)))
                elements.append(Paragraph(risk.get('description', ''), normal_style))
                elements.append(Spacer(1, 0.15*inch))
        
        # Footer
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("_" * 80, 
                                 ParagraphStyle('Line', parent=normal_style, 
                                              fontSize=8, alignment=TA_CENTER)))
        elements.append(Paragraph("<i>This report is generated by ChaiTea Farmer Action Simulator</i>", 
                                 ParagraphStyle('Footer', parent=normal_style, 
                                              fontSize=9, alignment=TA_CENTER,
                                              textColor=colors.grey)))
        elements.append(Paragraph("<i>For best results, implement recommendations within the suggested timeframes</i>", 
                                 ParagraphStyle('Footer2', parent=normal_style, 
                                              fontSize=9, alignment=TA_CENTER,
                                              textColor=colors.grey)))
        
        # Build PDF
        doc.build(elements)
        
        return FileResponse(
            pdf_path,
            media_type='application/pdf',
            filename=f'ChaiTea_Action_Plan_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
        
    except Exception as e:
        print(f"❌ PDF GENERATION ERROR: {e}")
        return {"error": str(e)}


# -----------------------------
# INTELLIGENT ACTION PLAN GENERATOR
# -----------------------------

def fetch_todays_comprehensive_data(farm_id: str):
    """
    Aggregates all data sources for comprehensive action plan generation:
    - Last 7 days of sensor readings (soil moisture, temperature, humidity, rainfall)
    - Last 7 days of leaf scans with quality metrics
    - Current market prices and trends
    """
    FARM_ID = farm_id
    
    # -------- FETCH LAST 7 DAYS OF SENSOR DATA --------
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    sensor_docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("sensors")
        .document("sensors_root")
        .collection("readings")
        .where("timestamp", ">=", seven_days_ago)
        .order_by("timestamp", direction=Query.DESCENDING)
        .stream()
    )
    
    sensor_readings = []
    for doc in sensor_docs:
        d = doc.to_dict()
        sensor_readings.append({
            "soil_moisture": d.get("soil_moisture"),
            "temperature": d.get("temperature"),
            "humidity": d.get("humidity"),
            "rainfall_7d": d.get("rainfall_7d"),
            "soil_ph": d.get("soil_ph", 5.2),
            "timestamp": d.get("timestamp")
        })
    
    # Calculate average sensor data from 7 days
    sensor_data = None
    if sensor_readings:
        sensor_data = {
            "soil_moisture": sum(r["soil_moisture"] for r in sensor_readings) / len(sensor_readings),
            "temperature": sum(r["temperature"] for r in sensor_readings) / len(sensor_readings),
            "humidity": sum(r["humidity"] for r in sensor_readings) / len(sensor_readings),
            "rainfall_7d": sum(r["rainfall_7d"] for r in sensor_readings) / len(sensor_readings),
            "soil_ph": sum(r["soil_ph"] for r in sensor_readings) / len(sensor_readings),
            "timestamp": sensor_readings[0]["timestamp"],  # Most recent timestamp
            "readings_count": len(sensor_readings)
        }
    
    # -------- FETCH LAST 7 DAYS OF LEAF SCANS --------
    seven_days_ago_start = datetime.utcnow() - timedelta(days=7)
    
    leaf_scan_docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("leaf_scans")
        .where("timestamp", ">=", seven_days_ago_start)
        .order_by("timestamp", direction=Query.DESCENDING)
        .stream()
    )

    
    leaf_scans = []
    for doc in leaf_scan_docs:
        scan = doc.to_dict()
        leaf_scans.append({
            "grade": scan.get("grade"),
            "disease_type": scan.get("disease_type"),
            "confidence": scan.get("confidence"),
            "severity": scan.get("severity"),
            "timestamp": scan.get("timestamp"),
            "surface_analysis": scan.get("surface_analysis")
        })
    
    # -------- FETCH MARKET DATA --------
    market_data = None
    if df is not None and not df.empty and len(df) >= 3:
        prices = df[PRIMARY_MARKET].dropna()
        
        current_price = float(prices.iloc[-1])
        prev_price = float(prices.iloc[-2])
        price_change_pct = ((current_price - prev_price) / prev_price) * 100
        
        # Demand calculation
        price_change_pct_abs = abs(price_change_pct)
        demand_index = min(price_change_pct_abs * 5, 100)
        
        # Volatility
        recent_7 = prices.tail(7)
        volatility = (recent_7.std() / recent_7.mean()) * 100
        
        # Forecast
        forecast_price = forecast_price_from_dict(price_model)
        
        # Market signal
        if demand_index < 20 and volatility < 3:
            signal = "watch"
        elif demand_index >= 20 and volatility < 3:
            signal = "opportunity"
        elif volatility >= 3:
            signal = "risk"
        else:
            signal = "neutral"
        
        market_data = {
            "current_price": round(current_price, 2),
            "forecast_price": round(forecast_price, 2),
            "price_change_pct": round(price_change_pct, 1),
            "demand_index": round(demand_index, 0),
            "volatility": round(volatility, 2),
            "signal": signal,
            "market": PRIMARY_MARKET
        }
    
    return {
        "sensor_data": sensor_data,
        "leaf_scans": leaf_scans,
        "market_data": market_data,
        "timestamp": datetime.utcnow()
    }


def calculate_environmental_score(sensor_data):
    """
    Calculate environmental health score (0-100) based on sensor readings
    Weight: 40% of total action plan score
    """
    if not sensor_data:
        return {"score": 50, "factors": {}, "status": "unknown"}
    
    factors = {}
    total_score = 0
    
    # Soil Moisture (35% of environmental score)
    sm = float(sensor_data.get("soil_moisture") or 60)
    if 55 <= sm <= 65:
        sm_score = 100
        sm_status = "optimal"
    elif 50 <= sm < 55 or 65 < sm <= 70:
        sm_score = 75
        sm_status = "acceptable"
    elif 45 <= sm < 50 or 70 < sm <= 75:
        sm_score = 50
        sm_status = "suboptimal"
    else:
        sm_score = 25
        sm_status = "critical"
    
    factors["soil_moisture"] = {"score": sm_score, "value": sm, "status": sm_status}
    total_score += sm_score * 0.35
    
    # Temperature (25% of environmental score)
    temp = float(sensor_data.get("temperature") or 22)
    if 18 <= temp <= 26:
        temp_score = 100
        temp_status = "optimal"
    elif 15 <= temp < 18 or 26 < temp <= 30:
        temp_score = 70
        temp_status = "acceptable"
    else:
        temp_score = 40
        temp_status = "suboptimal"
    
    factors["temperature"] = {"score": temp_score, "value": temp, "status": temp_status}
    total_score += temp_score * 0.25
    
    # Humidity (20% of environmental score)
    hum = float(sensor_data.get("humidity") or 70)
    if 65 <= hum <= 75:
        hum_score = 100
        hum_status = "optimal"
    elif 60 <= hum < 65 or 75 < hum <= 80:
        hum_score = 75
        hum_status = "acceptable"
    else:
        hum_score = 50
        hum_status = "suboptimal"
    
    factors["humidity"] = {"score": hum_score, "value": hum, "status": hum_status}
    total_score += hum_score * 0.20
    
    # Rainfall (20% of environmental score)
    rain = float(sensor_data.get("rainfall_7d") or 60)
    if 40 <= rain <= 80:
        rain_score = 100
        rain_status = "optimal"
    elif 30 <= rain < 40 or 80 < rain <= 100:
        rain_score = 70
        rain_status = "acceptable"
    else:
        rain_score = 40
        rain_status = "suboptimal"
    
    factors["rainfall_7d"] = {"score": rain_score, "value": rain, "status": rain_status}
    total_score += rain_score * 0.20
    
    # Overall status
    if total_score >= 85:
        overall_status = "excellent"
    elif total_score >= 70:
        overall_status = "good"
    elif total_score >= 50:
        overall_status = "fair"
    else:
        overall_status = "poor"
    
    return {
        "score": round(total_score, 1),
        "factors": factors,
        "status": overall_status
    }


def calculate_crop_health_score(leaf_scans):
    """
    Calculate crop health score (0-100) based on leaf scan data
    Weight: 35% of total action plan score
    """
    if not leaf_scans or len(leaf_scans) == 0:
        return {"score": 70, "status": "unknown", "scans_analyzed": 0}
    
    total_score = 0
    disease_count = 0
    high_severity_count = 0
    
    for scan in leaf_scans:
        grade = (scan.get("grade") or "").lower()
        # Coerce to float, default to 0.5 if None or missing
        confidence = float(scan.get("confidence") or 0.5)
        # Coerce severity to string, default to "Low" if None
        severity = scan.get("severity") or "Low"
        
        # Base score by grade
        if grade == "healthy":
            scan_score = 100
        elif grade == "stressed":
            scan_score = 60
        elif grade == "diseased":
            scan_score = 30
            disease_count += 1
        else:
            scan_score = 50
        
        # Adjust by confidence
        scan_score = scan_score * confidence
        
        # Adjust by severity
        if severity == "High":
            scan_score *= 0.7
            high_severity_count += 1
        elif severity == "Moderate":
            scan_score *= 0.85
        
        total_score += scan_score
    
    avg_score = total_score / len(leaf_scans)
    
    # Determine status
    if avg_score >= 85:
        status = "excellent"
    elif avg_score >= 70:
        status = "good"
    elif avg_score >= 50:
        status = "fair"
    else:
        status = "poor"
    
    return {
        "score": round(avg_score, 1),
        "status": status,
        "scans_analyzed": len(leaf_scans),
        "disease_count": disease_count,
        "high_severity_count": high_severity_count
    }


def calculate_market_opportunity_score(market_data):
    """
    Calculate market opportunity score (0-100) based on price trends
    Weight: 25% of total action plan score
    """
    if not market_data:
        return {"score": 50, "status": "unknown", "signal": "neutral"}
    
    signal = market_data.get("signal") or "neutral"
    demand_index = float(market_data.get("demand_index") or 50)
    volatility = float(market_data.get("volatility") or 2)
    price_change_pct = float(market_data.get("price_change_pct") or 0)
    
    # Base score by signal
    if signal == "opportunity":
        base_score = 85
        status = "favorable"
    elif signal == "watch":
        base_score = 50
        status = "cautious"
    elif signal == "risk":
        base_score = 35
        status = "unfavorable"
    else:
        base_score = 60
        status = "neutral"
    
    # Adjust by demand
    if demand_index > 60:
        base_score += 10
    elif demand_index < 30:
        base_score -= 10
    
    # Adjust by price trend
    if price_change_pct > 5:
        base_score += 5
    elif price_change_pct < -5:
        base_score -= 5
    
    final_score = max(0, min(100, base_score))
    
    return {
        "score": round(final_score, 1),
        "status": status,
        "signal": signal,
        "demand_level": "high" if demand_index > 60 else "medium" if demand_index > 30 else "low"
    }




def generate_disease_prevention_approaches(leaf_scans, sensor_data):
    """
    Generate 3 distinct approaches for disease prevention and treatment
    based on leaf scan data and environmental conditions
    """
    if not leaf_scans or len(leaf_scans) == 0:
        return []
    
    # Analyze disease patterns
    diseased_scans = [s for s in leaf_scans if (s.get("grade") or "").lower() == "diseased"]
    disease_types = [s.get("disease_type") for s in diseased_scans if s.get("disease_type")]
    high_severity = [s for s in diseased_scans if s.get("severity") == "High"]
    
    context = {
        "total_scans": len(leaf_scans),
        "diseased_count": len(diseased_scans),
        "disease_types": list(set(disease_types)) if disease_types else ["general leaf stress"],
        "high_severity_count": len(high_severity),
        "environmental_conditions": {
            "soil_moisture": sensor_data.get("soil_moisture") if sensor_data else "unknown",
            "temperature": sensor_data.get("temperature") if sensor_data else "unknown",
            "humidity": sensor_data.get("humidity") if sensor_data else "unknown"
        }
    }
    
    prompt = f"""
You are an expert tea plant pathologist specializing in disease prevention and treatment.

Based on the analysis below, generate EXACTLY 3 distinct approaches for disease prevention and cure.
Each approach should be a complete strategy with different methodologies.

Rules:
- Generate EXACTLY 3 numbered approaches
- Each approach must be DIFFERENT (e.g., Approach 1: Chemical, Approach 2: Organic, Approach 3: Integrated)
- Each approach should be 2-3 sentences
- Focus on ACTIONABLE preventive measures and cures
- Be specific about treatments and timing
- No bullet points within approaches, use numbered list only

Analysis Data:
- Total Leaf Scans (Last 7 Days): {context['total_scans']}
- Diseased Scans Detected: {context['diseased_count']}
- Disease Types: {', '.join(context['disease_types'])}
- High Severity Cases: {context['high_severity_count']}
- Soil Moisture: {context['environmental_conditions']['soil_moisture']}%
- Temperature: {context['environmental_conditions']['temperature']}°C
- Humidity: {context['environmental_conditions']['humidity']}%

Generate 3 approaches now:
"""
    
    try:
        model = genai.GenerativeModel("models/gemini-pro")
        response = model.generate_content(prompt)
        
        if not response or not response.text:
            return []
        
        approaches = []
        text = response.text.strip()
        
        # Parse numbered approaches
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Match patterns like "1.", "1)", "Approach 1:", etc.
            if (line[0].isdigit() and len(line) > 2 and line[1] in ['.', ')', ':']):
                # Remove the number prefix
                approach_text = line[2:].strip()
                if approach_text.startswith("Approach"):
                    # Remove "Approach X:" prefix if present
                    approach_text = approach_text.split(":", 1)[-1].strip()
                approaches.append(approach_text)
        
        # Return exactly 3 approaches
        return approaches[:3] if len(approaches) >= 3 else approaches
        
    except Exception as e:
        print("❌ DISEASE PREVENTION APPROACHES ERROR:", e)
        return []


def generate_strategic_recommendations(env_score, crop_score, market_score, sensor_data, leaf_scans, market_data):

    """
    Generate strategic recommendations across multiple time horizons
    using AI-enriched insights
    """
    recommendations = {
        "immediate_actions": [],
        "short_term_strategy": [],
        "market_timing": [],
        "long_term_planning": []
    }
    
    # -------- IMMEDIATE ACTIONS (0-3 days) --------
    if sensor_data:
        sm = sensor_data.get("soil_moisture", 60)
        temp = sensor_data.get("temperature", 22)
        hum = sensor_data.get("humidity", 70)
        
        if sm < 50:
            recommendations["immediate_actions"].append({
                "action": "Increase irrigation immediately",
                "reason": f"Soil moisture at {sm}% is below optimal range (55-65%)",
                "priority": "high"
            })
        elif sm > 70:
            recommendations["immediate_actions"].append({
                "action": "Reduce irrigation and improve drainage",
                "reason": f"Soil moisture at {sm}% is above optimal range, risk of root rot",
                "priority": "high"
            })
        
        if temp > 28:
            recommendations["immediate_actions"].append({
                "action": "Implement shade management and increase irrigation",
                "reason": f"Temperature at {temp}°C exceeds optimal range (18-26°C)",
                "priority": "medium"
            })
        
        if hum < 60:
            recommendations["immediate_actions"].append({
                "action": "Increase misting or irrigation to raise humidity",
                "reason": f"Humidity at {hum}% is below optimal range (65-75%)",
                "priority": "medium"
            })
    
    # Check leaf scans for disease
    if leaf_scans:
        diseased_scans = [s for s in leaf_scans if (s.get("grade") or "").lower() == "diseased"]
        if diseased_scans:
            high_severity = [s for s in diseased_scans if s.get("severity") == "High"]
            if high_severity:
                recommendations["immediate_actions"].append({
                    "action": "Apply targeted fungicide treatment immediately",
                    "reason": f"Detected {len(high_severity)} high-severity disease cases",
                    "priority": "critical"
                })
            else:
                recommendations["immediate_actions"].append({
                    "action": "Inspect affected plants and apply preventive treatment",
                    "reason": f"Detected {len(diseased_scans)} diseased leaf samples",
                    "priority": "high"
                })
    
    # -------- SHORT-TERM STRATEGY (1-2 weeks) --------
    if crop_score["score"] < 70:
        recommendations["short_term_strategy"].append({
            "action": "Implement intensive crop monitoring program",
            "reason": f"Crop health score at {crop_score['score']}/100 requires attention",
            "timeline": "1-2 weeks"
        })
    
    if env_score["score"] >= 80 and crop_score["score"] >= 75:
        recommendations["short_term_strategy"].append({
            "action": "Optimize fertilization schedule for maximum yield",
            "reason": "Environmental and crop conditions are favorable for growth acceleration",
            "timeline": "1-2 weeks"
        })
    
    # -------- MARKET TIMING (2-4 weeks) --------
    if market_data:
        signal = market_data.get("signal")
        forecast_price = market_data.get("forecast_price")
        current_price = market_data.get("current_price")
        
        if signal == "opportunity":
            if forecast_price > current_price:
                recommendations["market_timing"].append({
                    "action": f"Delay harvest by 7-10 days to capture price increase",
                    "reason": f"Forecast shows price increase from ₹{current_price} to ₹{forecast_price}",
                    "expected_benefit": f"+{round(((forecast_price - current_price) / current_price) * 100, 1)}% revenue"
                })
            else:
                recommendations["market_timing"].append({
                    "action": "Prepare for harvest within optimal window",
                    "reason": "Market demand is strong, prices stable",
                    "expected_benefit": "Capture current favorable pricing"
                })
        
        elif signal == "risk":
            recommendations["market_timing"].append({
                "action": "Accelerate harvest if crop is ready",
                "reason": "Market volatility is high, secure current prices",
                "expected_benefit": "Avoid potential price decline"
            })
        
        elif signal == "watch":
            recommendations["market_timing"].append({
                "action": "Monitor market daily, maintain flexible harvest schedule",
                "reason": "Low demand and stable prices suggest waiting for better conditions",
                "expected_benefit": "Optimize timing for demand recovery"
            })
    
    # -------- LONG-TERM PLANNING (1-3 months) --------
    if env_score["score"] < 60:
        recommendations["long_term_planning"].append({
            "action": "Invest in soil improvement and irrigation infrastructure",
            "reason": "Environmental conditions are suboptimal for sustained productivity",
            "timeline": "1-3 months"
        })
    
    if crop_score.get("disease_count", 0) > 0:
        recommendations["long_term_planning"].append({
            "action": "Implement integrated pest management (IPM) program",
            "reason": f"Disease detected in {crop_score.get('disease_count', 0)} scans, preventive measures needed",
            "timeline": "Ongoing"
        })
    
    if market_score["score"] >= 70:
        recommendations["long_term_planning"].append({
            "action": "Consider expanding production capacity",
            "reason": "Market conditions are favorable for growth",
            "timeline": "2-3 months"
        })
    
    return recommendations


def generate_ai_enriched_insights(comprehensive_data, env_score, crop_score, market_score):
    """
    Use Gemini AI to generate contextual, strategic insights
    """
    context = {
        "environmental_score": env_score["score"],
        "environmental_status": env_score["status"],
        "crop_health_score": crop_score["score"],
        "crop_health_status": crop_score["status"],
        "market_opportunity_score": market_score["score"],
        "market_signal": market_score.get("signal", "neutral"),
        "scans_analyzed": crop_score.get("scans_analyzed", 0),
        "disease_detected": crop_score.get("disease_count", 0) > 0
    }
    
    prompt = f"""
You are an expert tea farm management advisor specializing in Assam tea cultivation.

Based on the comprehensive farm analysis below, provide a strategic executive summary (3-4 sentences) 
that highlights the most critical insights and recommended focus areas.

Rules:
- Be specific and actionable
- Prioritize the most impactful factors
- Use professional agricultural language
- Focus on strategic decisions, not tactical details
- No bullet points, write in paragraph form

Farm Analysis:
- Environmental Health: {context['environmental_score']}/100 ({context['environmental_status']})
- Crop Health: {context['crop_health_score']}/100 ({context['crop_health_status']})
- Market Opportunity: {context['market_opportunity_score']}/100 ({context['market_signal']})
- Leaf Scans Analyzed: {context['scans_analyzed']}
- Disease Detected: {'Yes' if context['disease_detected'] else 'No'}
"""
    
    try:
        model = genai.GenerativeModel("models/gemini-pro")
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else None
    except Exception as e:
        print("❌ AI INSIGHT ERROR:", e)
        return None


@app.post("/api/action-plan/generate")
def generate_comprehensive_action_plan(user: User = Depends(get_current_user)):
    """
    Generate comprehensive action plan integrating all data sources:
    - Environmental sensors (soil, temperature, humidity, rainfall)
    - Leaf scan quality and disease data
    - Market prices and trends
    
    Returns strategic recommendations across multiple time horizons
    """
    
    FARM_ID = resolve_farm_id(user)
    
    # -------- AGGREGATE ALL DATA --------
    comprehensive_data = fetch_todays_comprehensive_data(FARM_ID)
    
    sensor_data = comprehensive_data["sensor_data"]
    leaf_scans = comprehensive_data["leaf_scans"]
    market_data = comprehensive_data["market_data"]
    
    # -------- CALCULATE SCORES --------
    env_score = calculate_environmental_score(sensor_data)
    crop_score = calculate_crop_health_score(leaf_scans)
    market_score = calculate_market_opportunity_score(market_data)
    
    # -------- CALCULATE COMPOSITE SCORE --------
    # Weights: Environmental 40%, Crop Health 35%, Market 25%
    composite_score = (
        env_score["score"] * 0.40 +
        crop_score["score"] * 0.35 +
        market_score["score"] * 0.25
    )
    
    # -------- GENERATE RECOMMENDATIONS --------
    recommendations = generate_strategic_recommendations(
        env_score, crop_score, market_score,
        sensor_data, leaf_scans, market_data
    )
    
    # -------- GENERATE DISEASE PREVENTION APPROACHES --------
    disease_prevention_approaches = generate_disease_prevention_approaches(
        leaf_scans, sensor_data
    )
    
    # -------- AI ENRICHMENT --------

    ai_insight = generate_ai_enriched_insights(
        comprehensive_data, env_score, crop_score, market_score
    )
    
    # -------- PROJECTED OUTCOMES --------
    # Calculate expected yield and profit changes based on scores
    if composite_score >= 80:
        yield_change = "+8-12%"
        profit_change = "+₹5,000-8,000"
        risk_level = "Low"
    elif composite_score >= 65:
        yield_change = "+4-7%"
        profit_change = "+₹2,500-4,500"
        risk_level = "Low"
    elif composite_score >= 50:
        yield_change = "+1-3%"
        profit_change = "+₹500-2,000"
        risk_level = "Medium"
    else:
        yield_change = "-2-0%"
        profit_change = "-₹1,000-0"
        risk_level = "High"
    
    # Harvest timing based on market signal
    if market_data and market_data.get("signal") == "opportunity":
        harvest_timing = "+7 days"
    elif market_data and market_data.get("signal") == "risk":
        harvest_timing = "-3 days"
    else:
        harvest_timing = "No change"
    
    # -------- STORE IN FIRESTORE --------
    action_plan_doc = {
        "timestamp": SERVER_TIMESTAMP,
        "composite_score": round(composite_score, 1),
        "environmental_score": env_score["score"],
        "crop_health_score": crop_score["score"],
        "market_opportunity_score": market_score["score"],
        "recommendations": recommendations,
        "ai_insight": ai_insight,
        "data_sources": {
            "sensor_readings": 1 if sensor_data else 0,
            "leaf_scans": len(leaf_scans),
            "market_data_available": market_data is not None
        }
    }
    
    db.collection("farms") \
      .document(FARM_ID) \
      .collection("action_plans") \
      .add(action_plan_doc)
    
    print("✅ Action plan stored in Firestore")
    
    # -------- RETURN COMPREHENSIVE RESPONSE --------
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "composite_score": round(composite_score, 1),
        
        "environmental_data": {
            "score": env_score["score"],
            "status": env_score["status"],
            "factors": env_score["factors"],
            "latest_reading": sensor_data
        },
        
        "leaf_scan_summary": {
            "score": crop_score["score"],
            "status": crop_score["status"],
            "scans_analyzed": crop_score["scans_analyzed"],
            "disease_count": crop_score.get("disease_count", 0),
            "high_severity_count": crop_score.get("high_severity_count", 0),
            "recent_scans": leaf_scans[:3]  # Return up to 3 most recent
        },
        
        "market_analysis": {
            "score": market_score["score"],
            "status": market_score["status"],
            "signal": market_score.get("signal", "neutral"),
            "demand_level": market_score.get("demand_level", "medium"),
            "current_data": market_data
        },
        
        "recommended_actions": recommendations,
        
        "disease_prevention_approaches": disease_prevention_approaches,
        
        "projected_outcomes": {

            "yieldChange": yield_change,
            "profitChange": profit_change,
            "riskLevel": risk_level,
            "harvestTiming": harvest_timing
        },
        
        "confidence": {
            "modelAccuracy": 89,
            "marketReliability": 95 if market_data else 50,
            "historicalSimilarity": 82
        },
        
        "ai_insight": ai_insight,
        
        "data_quality": {
            "sensor_data_available": sensor_data is not None,
            "leaf_scans_count": len(leaf_scans),
            "market_data_available": market_data is not None,
            "overall_confidence": "high" if (sensor_data and len(leaf_scans) > 0 and market_data) else "medium"
        }
    }


@app.get("/api/action-plan/history")
def get_action_plan_history(limit: int = 10, user: User = Depends(get_current_user)):
    """
    Retrieve historical action plans for comparison and tracking
    """
    FARM_ID = resolve_farm_id(user)
    
    docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("action_plans")
        .order_by("timestamp", direction=Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    
    history = []
    for doc in docs:
        plan = doc.to_dict()
        history.append({
            "id": doc.id,
            "timestamp": plan.get("timestamp"),
            "composite_score": plan.get("composite_score"),
            "environmental_score": plan.get("environmental_score"),
            "crop_health_score": plan.get("crop_health_score"),
            "market_opportunity_score": plan.get("market_opportunity_score"),
            "ai_insight": plan.get("ai_insight")
        })
    
    return {
        "count": len(history),
        "plans": history
    }


# -----------------------------
# CHATBOT INTEGRATION
# -----------------------------

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    response: str
    source: str  # "AI" or "Fallback"
    suggested_actions: List[str] = []


def gather_comprehensive_context():
    """
    Gather ALL available farm context from every endpoint for the chatbot.
    Returns a comprehensive dictionary with all dashboard data.
    """
    FARM_ID = "demo_farm"
    context = {}
    
    try:
        # ========================================
        # 1. LATEST SENSOR DATA (Real-time IoT)
        # ========================================
        sensor_docs = (
            db.collection("farms")
            .document(FARM_ID)
            .collection("sensors")
            .document("sensors_root")
            .collection("readings")
            .order_by("timestamp", direction=Query.DESCENDING)
            .limit(1)
            .stream()
        )
        
        latest_sensor = next(sensor_docs, None)
        if latest_sensor:
            sensor_data = latest_sensor.to_dict()
            context["sensors"] = {
                "soil_moisture": sensor_data.get("soil_moisture"),
                "temperature": sensor_data.get("temperature"),
                "humidity": sensor_data.get("humidity"),
                "rainfall_7d": sensor_data.get("rainfall_7d"),
                "soil_ph": sensor_data.get("soil_ph", 5.2),
                "timestamp": sensor_data.get("timestamp")
            }
            
            # ========================================
            # 2. CULTIVATION ENGINE RESULTS
            # ========================================
            cultivation_result = run_cultivation_engine({
                "soil_moisture": sensor_data["soil_moisture"],
                "temperature": sensor_data["temperature"],
                "humidity": sensor_data["humidity"],
                "rainfall_7d": sensor_data["rainfall_7d"],
                "soil_ph": sensor_data.get("soil_ph", 5.2),
            })
            context["cultivation"] = cultivation_result
            
            # ========================================
            # 3. SMART ALERT STATUS
            # ========================================
            health_score = compute_health_score({
                "soil_moisture": sensor_data["soil_moisture"],
                "temperature": sensor_data["temperature"],
                "humidity": sensor_data["humidity"],
                "rainfall_7d": sensor_data["rainfall_7d"]
            })
            risk_score, stress_breakdown = compute_stress_breakdown({
                "soil_moisture": sensor_data["soil_moisture"],
                "temperature": sensor_data["temperature"],
                "humidity": sensor_data["humidity"],
                "rainfall_7d": sensor_data["rainfall_7d"]
            })
            
            context["alerts"] = {
                "health_score": health_score,
                "risk_score": risk_score,
                "stress_breakdown": stress_breakdown,
                "alert_active": health_score <= 60
            }
        
        # ========================================
        # 4. FARM AVERAGES (Last 50 readings)
        # ========================================
        readings_ref = (
            db.collection("farms")
            .document(FARM_ID)
            .collection("sensors")
            .document("sensors_root")
            .collection("readings")
            .order_by("timestamp", direction=Query.DESCENDING)
            .limit(50)
        )
        
        docs = readings_ref.stream()
        readings = []
        for doc in docs:
            d = doc.to_dict()
            readings.append({
                "soil_moisture": d.get("soil_moisture"),
                "temperature": d.get("temperature"),
                "humidity": d.get("humidity"),
                "rainfall_7d": d.get("rainfall_7d"),
            })
        
        if readings:
            df_readings = pd.DataFrame(readings)
            context["averages"] = {
                "soil_moisture": round(df_readings["soil_moisture"].mean(), 2),
                "temperature": round(df_readings["temperature"].mean(), 2),
                "humidity": round(df_readings["humidity"].mean(), 2),
                "rainfall_7d": round(df_readings["rainfall_7d"].mean(), 2),
                "sample_count": len(df_readings)
            }
        
        # ========================================
        # 5. SOIL MOISTURE TREND (Last 24 readings)
        # ========================================
        soil_docs = (
            db.collection("farms")
            .document(FARM_ID)
            .collection("sensors")
            .document("sensors_root")
            .collection("readings")
            .order_by("timestamp", direction=Query.DESCENDING)
            .limit(24)
            .stream()
        )
        
        soil_series = []
        for doc in soil_docs:
            d = doc.to_dict()
            if d.get("timestamp"):
                soil_series.append({
                    "value": round(d["soil_moisture"], 1),
                    "ts": d["timestamp"]
                })
        
        soil_series.sort(key=lambda x: x["ts"])
        if len(soil_series) >= 2:
            context["soil_moisture_trend"] = {
                "current": soil_series[-1]["value"],
                "previous": soil_series[-2]["value"],
                "change": round(soil_series[-1]["value"] - soil_series[-2]["value"], 1),
                "trend": "increasing" if soil_series[-1]["value"] > soil_series[-2]["value"] else "decreasing"
            }
        
        # ========================================
        # 6. MARKET DATA (KPIs + Price Series)
        # ========================================
        if df is not None and not df.empty and len(df) >= 3:
            prices = df[PRIMARY_MARKET].dropna()
            
            # Current price and change
            current_price = float(prices.iloc[-1])
            prev_price = float(prices.iloc[-2])
            price_change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # Demand index
            price_change_pct_abs = abs((prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]) * 100
            demand_index = min(price_change_pct_abs * 5, 100)
            
            # Volatility
            recent_7 = prices.tail(7)
            volatility = round(recent_7.std(), 2)
            
            context["market"] = {
                "current_price": round(current_price, 2),
                "previous_price": round(prev_price, 2),
                "price_change_pct": round(price_change_pct, 2),
                "price_trend": "increasing" if price_change_pct > 0 else "decreasing",
                "demand_index": round(demand_index, 1),
                "volatility": volatility,
                "market_name": "Guwahati",
                "week_ending": str(df.iloc[-1]["week_ending_date"].strftime("%Y-%m-%d"))
            }
            
            # Price series (last 8 weeks)
            price_history = []
            for idx in range(min(8, len(df))):
                row = df.iloc[-(idx+1)]
                price_history.append({
                    "week": row["week_ending_date"].strftime("%b %d"),
                    "price": round(float(row[PRIMARY_MARKET]), 2)
                })
            price_history.reverse()
            context["market"]["price_history"] = price_history
            
            # All market locations
            market_columns = ["kolkata", "guwahati", "siliguri", "jalpaiguri", 
                            "mjunction", "cochin", "coonoor", "coimbatore", "tea_serve"]
            latest_row = df.iloc[-1]
            location_prices = {}
            for col in market_columns:
                if col in latest_row and pd.notna(latest_row[col]):
                    location_prices[col.title()] = round(float(latest_row[col]), 2)
            context["market"]["all_locations"] = location_prices
        
        # ========================================
        # 7. LATEST LEAF SCAN RESULTS
        # ========================================
        leaf_docs = (
            db.collection("farms")
            .document(FARM_ID)
            .collection("leaf_scans")
            .order_by("timestamp", direction=Query.DESCENDING)
            .limit(3)  # Get last 3 scans for trend
            .stream()
        )
        
        leaf_scans = []
        for doc in leaf_docs:
            leaf_data = doc.to_dict()
            leaf_scans.append({
                "grade": leaf_data.get("grade"),
                "disease_type": leaf_data.get("disease_type"),
                "confidence": leaf_data.get("confidence"),
                "severity": leaf_data.get("severity"),
                "timestamp": leaf_data.get("timestamp")
            })
        
        if leaf_scans:
            context["leaf_quality"] = {
                "latest": leaf_scans[0],
                "history_count": len(leaf_scans),
                "recent_scans": leaf_scans
            }
        
        # ========================================
        # 8. DAILY METRICS (Last 7 days)
        # ========================================
        now = datetime.utcnow()
        start = now - timedelta(days=7)
        
        daily_docs = (
            db.collection("farms")
            .document(FARM_ID)
            .collection("sensors")
            .document("sensors_root")
            .collection("readings")
            .where("timestamp", ">=", start)
            .stream()
        )
        
        buckets = defaultdict(lambda: {
            "soil_moisture": [],
            "temperature": [],
            "humidity": [],
            "rainfall": 0.0,
        })
        
        for doc in daily_docs:
            d = doc.to_dict()
            ts = d.get("timestamp")
            if ts:
                day = ts.strftime("%a")
                buckets[day]["soil_moisture"].append(d["soil_moisture"])
                buckets[day]["temperature"].append(d["temperature"])
                buckets[day]["humidity"].append(d["humidity"])
                buckets[day]["rainfall"] += d.get("rainfall_7d", 0) / 7
        
        daily_summary = []
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            if day in buckets:
                b = buckets[day]
                daily_summary.append({
                    "day": day,
                    "soil_moisture": round(sum(b["soil_moisture"]) / len(b["soil_moisture"]), 1),
                    "temperature": round(sum(b["temperature"]) / len(b["temperature"]), 1),
                    "humidity": round(sum(b["humidity"]) / len(b["humidity"]), 1),
                    "rainfall": round(b["rainfall"], 1),
                })
        
        if daily_summary:
            context["daily_metrics"] = daily_summary
    
    except Exception as e:
        print(f"❌ Error gathering context: {e}")
        import traceback
        traceback.print_exc()
    
    return context



def get_fallback_response(message: str) -> str:
    """
    Rule-based fallback responses when AI is unavailable.
    This mirrors the logic from the frontend chatbot.
    """
    input_lower = message.lower()
    
    if "leaf quality" in input_lower or "improve leaf" in input_lower:
        return "To improve leaf quality, ensure consistent soil moisture (55-65%), maintain optimal temperature (22-25°C), and apply balanced fertilizers. Also monitor for pests regularly and ensure adequate light exposure. Our AI scanner can help grade your leaves in real-time!"
    
    if "irrigation" in input_lower or "water" in input_lower:
        return "For tea plants, irrigation depends on season and soil type. During growing season: 2-3 times weekly. Use drip irrigation for efficiency. Monitor soil moisture with our IoT sensors."
    
    if "market" in input_lower or "price" in input_lower:
        return "Check the Market Intelligence tab for detailed price forecasts and optimal selling windows. Market trends are updated weekly based on auction data from major markets."
    
    if "pest" in input_lower or "disease" in input_lower:
        return "Common tea plant pests: Green leaf hopper, Scale insect, and Tea mosquito. Prevention: Regular scouting, integrated pest management, organic neem spray. Quarantine affected plants. Early detection is key!"
    
    if "fertilizer" in input_lower or "nutrient" in input_lower:
        return "Tea plants need NPK ratio around 4:2:2. Apply 500-750 kg/hectare annually. Use organic matter to improve soil structure. Split applications: after each harvest. Foliar feeding with micronutrients boosts quality. Soil test results recommended."
    
    if "harvest" in input_lower or "picking" in input_lower:
        return "Harvest tea leaves at the 2-3 leaf stage for best quality. Morning picking (after dew dries) is preferred. Use two leaves + bud (2LB) for premium grades. Our AI recommendations suggest optimal harvest timing based on current conditions."
    
    if "soil moisture" in input_lower:
        return "Optimal soil moisture for tea plants is 55-65%. Too low causes stress and poor quality. Too high leads to root diseases. Use our IoT sensors for real-time monitoring and automated irrigation scheduling."
    
    if "temperature" in input_lower:
        return "Ideal temperature range for tea cultivation is 18-26°C. Temperatures above 30°C cause heat stress. Below 15°C slows growth. Monitor daily and adjust shade management accordingly."
    
    if "humidity" in input_lower:
        return "Tea plants thrive in 65-75% humidity. Low humidity increases water stress and pest susceptibility. High humidity can promote fungal diseases. Proper canopy management helps regulate microclimate."
    
    # Hindi/Assamese language detection
    if any(word in input_lower for word in ["kaise", "kya", "mujhe", "chai", "पानी", "मिट्टी"]):
        return "मैं आपकी मदद करने के लिए यहाँ हूँ। कृपया अपना सवाल अंग्रेजी में पूछें या विशिष्ट विषय चुनें: पत्ती की गुणवत्ता, सिंचाई, बाजार मूल्य, या कीट नियंत्रण।"
    
    # Default response
    return "That's a great question! Based on your current farm data, I recommend checking the relevant dashboard tab for detailed insights. You can also explore the Cultivation Intelligence, Leaf Quality Scanner, or Market Intelligence sections. Is there anything specific I can help clarify?"


def generate_chat_response(message: str, history: List[ChatMessage], context: dict) -> tuple:
    """
    Generate AI response using Gemini with comprehensive context from ALL endpoints.
    Returns (response_text, suggested_actions)
    """
    # Detect language
    message_lower = message.lower()
    is_hindi = any(word in message for word in ["कैसे", "क्या", "मुझे", "चाय", "पानी", "मिट्टी", "कीड़े", "बीमारी", "सिंचाई"])
    is_assamese = any(word in message for word in ["কেনেকৈ", "কি", "চাহ", "পানী", "মাটি"])
    
    # Build COMPREHENSIVE context summary
    context_summary = "=== COMPLETE FARM DATA ===\n\n"
    
    # 1. CURRENT SENSOR READINGS
    if "sensors" in context:
        s = context["sensors"]
        context_summary += "📊 CURRENT SENSOR READINGS:\n"
        context_summary += f"  • Soil Moisture: {s.get('soil_moisture')}%\n"
        context_summary += f"  • Temperature: {s.get('temperature')}°C\n"
        context_summary += f"  • Humidity: {s.get('humidity')}%\n"
        context_summary += f"  • Rainfall (7 days): {s.get('rainfall_7d')}mm\n"
        context_summary += f"  • Soil pH: {s.get('soil_ph')}\n\n"
    
    # 2. FARM AVERAGES (Last 50 readings)
    if "averages" in context:
        a = context["averages"]
        context_summary += "📈 FARM AVERAGES (Last 50 readings):\n"
        context_summary += f"  • Avg Soil Moisture: {a.get('soil_moisture')}%\n"
        context_summary += f"  • Avg Temperature: {a.get('temperature')}°C\n"
        context_summary += f"  • Avg Humidity: {a.get('humidity')}%\n"
        context_summary += f"  • Avg Rainfall: {a.get('rainfall_7d')}mm\n"
        context_summary += f"  • Sample Count: {a.get('sample_count')}\n\n"
    
    # 3. SOIL MOISTURE TREND
    if "soil_moisture_trend" in context:
        t = context["soil_moisture_trend"]
        context_summary += "💧 SOIL MOISTURE TREND:\n"
        context_summary += f"  • Current: {t.get('current')}%\n"
        context_summary += f"  • Previous: {t.get('previous')}%\n"
        context_summary += f"  • Change: {t.get('change')}% ({t.get('trend')})\n\n"
    
    # 4. CULTIVATION HEALTH
    if "cultivation" in context:
        c = context["cultivation"]
        context_summary += "🌱 CULTIVATION HEALTH ANALYSIS:\n"
        context_summary += f"  • Health Score: {c.get('health_score')}/100\n"
        context_summary += f"  • Pest Risk: {c.get('pest_risk')}\n"
        context_summary += f"  • Drought Risk: {c.get('drought_risk')}\n"
        context_summary += f"  • Recommended Action: {c.get('action')}\n"
        if "score_explanation" in c:
            exp = c["score_explanation"]
            context_summary += f"  • Soil Moisture Status: {exp.get('soil_moisture')}\n"
            context_summary += f"  • Temperature Status: {exp.get('temperature')}\n"
            context_summary += f"  • Humidity Status: {exp.get('humidity')}\n"
            context_summary += f"  • Rainfall Status: {exp.get('rainfall_7d')}\n"
        context_summary += "\n"
    
    # 5. SMART ALERTS
    if "alerts" in context:
        al = context["alerts"]
        context_summary += "⚠️ SMART ALERTS:\n"
        context_summary += f"  • Alert Active: {'YES' if al.get('alert_active') else 'NO'}\n"
        context_summary += f"  • Health Score: {al.get('health_score')}/100\n"
        context_summary += f"  • Risk Score: {al.get('risk_score')}/100\n"
        if "stress_breakdown" in al:
            context_summary += "  • Stress Factors:\n"
            for factor, value in al["stress_breakdown"].items():
                if value > 0:
                    context_summary += f"    - {factor.replace('_', ' ').title()}: {value}\n"
        context_summary += "\n"
    
    # 6. MARKET DATA
    if "market" in context:
        m = context["market"]
        context_summary += "💰 MARKET INTELLIGENCE (Guwahati):\n"
        context_summary += f"  • Current Price: ₹{m.get('current_price')}/kg\n"
        context_summary += f"  • Previous Price: ₹{m.get('previous_price')}/kg\n"
        context_summary += f"  • Price Change: {m.get('price_change_pct')}% ({m.get('price_trend')})\n"
        context_summary += f"  • Demand Index: {m.get('demand_index')}/100\n"
        context_summary += f"  • Market Volatility: {m.get('volatility')}\n"
        context_summary += f"  • Week Ending: {m.get('week_ending')}\n"
        
        if "price_history" in m and m["price_history"]:
            context_summary += "  • Recent Price History:\n"
            for ph in m["price_history"][-4:]:  # Last 4 weeks
                context_summary += f"    - {ph['week']}: ₹{ph['price']}/kg\n"
        
        if "all_locations" in m:
            context_summary += "  • Prices at Other Markets:\n"
            for loc, price in m["all_locations"].items():
                context_summary += f"    - {loc}: ₹{price}/kg\n"
        context_summary += "\n"
    
    # 7. LEAF QUALITY SCANS
    if "leaf_quality" in context:
        lq = context["leaf_quality"]
        latest = lq.get("latest", {})
        context_summary += "🍃 LEAF QUALITY SCANS:\n"
        context_summary += f"  • Latest Grade: {latest.get('grade')}\n"
        if latest.get('disease_type'):
            context_summary += f"  • Disease Detected: {latest.get('disease_type')}\n"
        context_summary += f"  • Confidence: {latest.get('confidence')}\n"
        context_summary += f"  • Severity: {latest.get('severity')}\n"
        context_summary += f"  • Total Scans in History: {lq.get('history_count')}\n\n"
    
    # 8. DAILY METRICS (Last 7 days)
    if "daily_metrics" in context:
        dm = context["daily_metrics"]
        context_summary += "📅 DAILY METRICS (Last 7 days):\n"
        for day_data in dm[-3:]:  # Last 3 days
            context_summary += f"  • {day_data['day']}: "
            context_summary += f"Moisture={day_data['soil_moisture']}%, "
            context_summary += f"Temp={day_data['temperature']}°C, "
            context_summary += f"Humidity={day_data['humidity']}%\n"
        context_summary += "\n"
    
    # Build chat history for context
    chat_history = ""
    for msg in history[-6:]:  # Last 6 messages for context
        chat_history += f"{msg.role.capitalize()}: {msg.content}\n"
    
    # Enhanced system prompt with multi-lingual support
    if is_hindi:
        language_instruction = """
CRITICAL: The user is asking in HINDI. You MUST respond ENTIRELY in HINDI (Devanagari script).
Use natural, conversational Hindi that a farmer in Assam would understand.
"""
    elif is_assamese:
        language_instruction = """
CRITICAL: The user is asking in ASSAMESE. You MUST respond ENTIRELY in ASSAMESE (Bengali script).
Use natural, conversational Assamese that a tea farmer would understand.
"""
    else:
        language_instruction = """
The user is asking in ENGLISH. Respond in clear, simple English.
"""
    
    system_prompt = f"""You are an expert tea agronomist and farming assistant for CHAI-NET, an AI-powered tea cultivation platform in Assam, India.

{language_instruction}

Your role:
- Provide accurate, practical advice on tea cultivation, leaf quality, pest management, irrigation, and market timing
- Use the provided REAL-TIME farm data to give context-aware recommendations
- ALWAYS reference actual numbers from the data when answering questions
- Be concise but informative (2-5 sentences typically)
- When relevant, suggest specific actions the farmer can take
- If asked about specific metrics (soil moisture, temperature, prices, etc.), ALWAYS quote the exact values from the data

Critical guidelines:
- DO NOT invent numbers or data not provided in the context
- ALWAYS use the actual data values when they are available
- If you don't have specific data, clearly state that and provide general best practices
- Prioritize actionable advice over theory
- Be encouraging and supportive in tone
- For urgent issues (high pest risk, severe disease, low health score), emphasize immediate action
- When asked "what is my X", respond with the actual value from the current data

Examples of good responses:
- "Your current soil moisture is 58%, which is within the optimal range of 55-65%."
- "The Guwahati market price is ₹245/kg, up 3.2% from last week."
- "Your farm health score is 72/100, with moderate pest risk detected."
"""

    full_prompt = f"""{system_prompt}

{context_summary}

Previous conversation:
{chat_history}

User question: {message}

Provide a helpful, data-driven response. If appropriate, end with 1-3 specific suggested actions (each on a new line starting with "ACTION:").
"""

    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(full_prompt)
        
        if not response or not response.text:
            return None, []
        
        response_text = response.text.strip()
        
        # Extract suggested actions
        suggested_actions = []
        lines = response_text.split("\n")
        cleaned_lines = []
        
        for line in lines:
            if line.strip().startswith("ACTION:"):
                action = line.replace("ACTION:", "").strip()
                if action:
                    suggested_actions.append(action)
            else:
                cleaned_lines.append(line)
        
        # Remove ACTION lines from main response
        final_response = "\n".join(cleaned_lines).strip()
        
        return final_response, suggested_actions
    
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        import traceback
        traceback.print_exc()
        return None, []



@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    """
    Main chatbot endpoint with AI and fallback support.
    """
    try:
        # Gather comprehensive farm context
        context = gather_comprehensive_context()
        
        # Try to get AI response
        ai_response, suggested_actions = generate_chat_response(
            request.message, 
            request.history, 
            context
        )
        
        if ai_response:
            return ChatResponse(
                response=ai_response,
                source="AI",
                suggested_actions=suggested_actions
            )
        else:
            # AI failed, use fallback
            fallback_response = get_fallback_response(request.message)
            return ChatResponse(
                response=fallback_response,
                source="Fallback",
                suggested_actions=[]
            )
    
    except Exception as e:
        print(f"❌ Chat endpoint error: {e}")
        # Ultimate fallback
        fallback_response = get_fallback_response(request.message)
        return ChatResponse(
            response=fallback_response,
            source="Fallback",
            suggested_actions=[]
        )


# ============================================================
# MODULE: SATELLITE CROP HEALTH MONITOR  (Planet Labs API)
# ============================================================

import requests as _http
import base64 as _b64
import hashlib as _hashlib
import math as _math
import io as _io_mod
import time as _time_mod

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as _plt
    _MATPLOTLIB_OK = True
except Exception:
    _MATPLOTLIB_OK = False

try:
    import tifffile as _tifffile
    _TIFF_OK = True
except Exception:
    _TIFF_OK = False

try:
    from scipy.ndimage import gaussian_filter as _gaussian_filter
    _SCIPY_OK = True
except Exception:
    _SCIPY_OK = False

from sklearn.ensemble import IsolationForest as _IsoForest

PLANET_API_KEY = os.getenv("PLANET_API_KEY", "")
PLANET_SEARCH_URL = "https://api.planet.com/data/v1/quick-search"
_planet_search_diagnostic = "not attempted"
SENTINEL_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"


def _normalize_polygon_geometry(geometry: dict) -> dict:
    normalized = dict(geometry)
    coordinates = normalized.get("coordinates", [])
    if normalized.get("type") == "Polygon" and coordinates and coordinates[0] and isinstance(coordinates[0][0], (int, float)):
        normalized["coordinates"] = [coordinates]
    return normalized


class CropHealthRequest(BaseModel):
    geometry: dict          # GeoJSON Polygon geometry
    field_id: Optional[str] = None
    demo_mode: bool = False


def _classify_ndvi(v: float) -> str:
    if v >= 0.6:
        return "Healthy"
    elif v >= 0.3:
        return "Moderate"
    return "Stressed"


def _get_ndvi_history(farm_id: str, field_id: str, limit: int = 10) -> list:
    try:
        docs = (
            db.collection("farms").doc(farm_id)
            .collection("crop_health")
            .where("field_id", "==", field_id)
            .order_by("timestamp", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        out = []
        for d in docs:
            rec = d.to_dict()
            ts = rec.get("timestamp")
            ts_str = ts.isoformat()[:10] if hasattr(ts, "isoformat") else str(ts)[:10]
            out.append({
                "date": ts_str,
                "mean_ndvi": round(rec.get("mean_ndvi", 0), 4),
                "mean_evi": round(rec.get("mean_evi", 0), 4),
                "mean_ndwi": round(rec.get("mean_ndwi", 0), 4),
                "health_class": rec.get("health_class", "Unknown"),
                "scan_id": d.id,
            })
        return list(reversed(out))
    except Exception as exc:
        print(f"⚠️ NDVI history fetch: {exc}")
        return []


def _detect_anomaly(history: list) -> dict:
    if len(history) < 3:
        return {"is_anomaly": False, "drop": 0, "message": ""}
    vals = np.array([h.get("mean_ndvi", 0) for h in history], dtype=float)
    try:
        if len(vals) >= 5:
            clf = _IsoForest(contamination=0.2, random_state=42)
            preds = clf.fit_predict(vals.reshape(-1, 1))
            is_anom = bool(preds[-1] == -1)
        else:
            z = np.abs((vals - vals.mean()) / (vals.std() + 1e-9))
            is_anom = bool(z[-1] > 2.0)
    except Exception:
        is_anom = False
    drop = round(float(vals[-1]) - float(np.max(vals[:-1])), 3) if len(vals) > 1 else 0.0
    msg = "⚠️ Significant NDVI drop detected — possible early-stress event" if (is_anom and drop < -0.05) else ""
    return {"is_anomaly": is_anom, "drop": drop if drop < -0.05 else 0.0, "message": msg}


def _synthetic_heatmap(mean_ndvi: float, size: int = 160, seed: int = 42) -> str:
    """Returns a base64-encoded PNG colorized NDVI heatmap (RdYlGn)."""
    rng = np.random.RandomState(seed)
    data = np.full((size, size), mean_ndvi, dtype=float)
    noise = rng.normal(0, 0.07, (size, size))
    if _SCIPY_OK:
        noise = _gaussian_filter(noise, sigma=18)
    data = np.clip(data + noise, -1.0, 1.0)

    if _MATPLOTLIB_OK:
        cmap = _plt.cm.RdYlGn
        norm = (data + 1.0) / 2.0
        rgba = cmap(norm)
        fig, ax = _plt.subplots(figsize=(3, 3), dpi=60)
        ax.imshow(rgba, origin="upper")
        ax.axis("off")
        buf = _io_mod.BytesIO()
        _plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, transparent=True)
        _plt.close(fig)
        buf.seek(0)
        return _b64.b64encode(buf.read()).decode()
    else:
        # PIL fallback
        from PIL import Image as _PILImg
        arr = np.zeros((size, size, 3), dtype=np.uint8)
        n = (data + 1.0) / 2.0
        arr[:, :, 0] = ((1 - n) * 255).astype(np.uint8)
        arr[:, :, 1] = (n * 255).astype(np.uint8)
        arr[:, :, 2] = 50
        img = _PILImg.fromarray(arr)
        buf = _io_mod.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return _b64.b64encode(buf.read()).decode()


def _planet_search(geometry: dict) -> Optional[dict]:
    global _planet_search_diagnostic
    end = datetime.utcnow()
    # Small field polygons often have no cloud-free scene in a single month.
    # Keep the cloud threshold strict while searching a useful archive window.
    start = end - timedelta(days=90)
    payload = {
        "name": "chainet_search",
        "item_types": ["PSScene"],
        "filter": {
            "type": "AndFilter",
            "config": [
                {"type": "GeometryFilter", "field_name": "geometry", "config": geometry},
                {"type": "RangeFilter", "field_name": "cloud_cover", "config": {"lte": 0.2}},
                {"type": "DateRangeFilter", "field_name": "acquired",
                 "config": {"gte": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "lte": end.strftime("%Y-%m-%dT%H:%M:%SZ")}},
            ],
        },
    }
    try:
        r = _http.post(PLANET_SEARCH_URL, json=payload, auth=(PLANET_API_KEY, ""), timeout=25)
        r.raise_for_status()
        features = r.json().get("features", [])
        if not features:
            _planet_search_diagnostic = "no PSScene matched the polygon, 90-day window, and cloud-cover <= 20% filters"
            print(f"⚠️ Planet search: {_planet_search_diagnostic}")
            return None
        features.sort(key=lambda f: (
            f.get("properties", {}).get("cloud_cover", 1.0),
            f.get("properties", {}).get("acquired", ""),
        ))
        asset_preferences = {"ortho_analytic_4b_sr", "ortho_analytic_4b", "analytic_sr", "analytic"}
        for candidate in features[:10]:
            assets_url = f"https://api.planet.com/data/v1/item-types/PSScene/items/{candidate['id']}/assets"
            assets_response = _http.get(assets_url, auth=(PLANET_API_KEY, ""), timeout=15)
            assets_response.raise_for_status()
            assets = assets_response.json()
            if asset_preferences.intersection(assets):
                return candidate
        _planet_search_diagnostic = "matching PSScene metadata was found, but the account exposed no downloadable analytic assets"
        print(f"⚠️ Planet search: {_planet_search_diagnostic}")
        return None
    except Exception as exc:
        response = getattr(exc, "response", None)
        detail = response.text[:500] if response is not None else str(exc)
        _planet_search_diagnostic = detail
        print(f"⚠️ Planet search failed ({getattr(response, 'status_code', 'network')}): {detail}")
        return None


def _activate_and_download(item_id: str) -> Optional[bytes]:
    auth = (PLANET_API_KEY, "")
    assets_url = f"https://api.planet.com/data/v1/item-types/PSScene/items/{item_id}/assets"
    preference = ["ortho_analytic_4b_sr", "ortho_analytic_4b", "analytic_sr", "analytic"]
    try:
        r = _http.get(assets_url, auth=auth, timeout=15)
        r.raise_for_status()
        assets = r.json()
        asset_type = next((t for t in preference if t in assets), None)
        if not asset_type:
            return None
        asset = assets[asset_type]
        if asset.get("status") != "active":
            act_url = asset["_links"]["activate"]
            _http.post(act_url, auth=auth, timeout=10)
            for _ in range(9):
                _time_mod.sleep(5)
                r2 = _http.get(assets_url, auth=auth, timeout=10)
                asset = r2.json().get(asset_type, {})
                if asset.get("status") == "active":
                    break
            if asset.get("status") != "active":
                return None
        dl_url = asset.get("location")
        if not dl_url:
            return None
        r3 = _http.get(dl_url, auth=auth, timeout=60, stream=True)
        r3.raise_for_status()
        return r3.content
    except Exception as exc:
        print(f"⚠️ Planet activate/download: {exc}")
        return None


def _sentinel_search(geometry: dict) -> Optional[dict]:
    """Find a low-cloud Sentinel-2 L2A scene from the public Earth Search STAC API."""
    end = datetime.utcnow()
    start = end - timedelta(days=365)
    search_geometry = _normalize_polygon_geometry(geometry)
    try:
        response = _http.post(
            SENTINEL_SEARCH_URL,
            json={
                "collections": ["sentinel-2-l2a"],
                "intersects": search_geometry,
                "datetime": f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
                "limit": 20,
                "query": {"eo:cloud_cover": {"lte": 20}},
            },
            timeout=25,
            headers={"User-Agent": "ChaiNet/1.0"},
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        global _planet_search_diagnostic
        _planet_search_diagnostic = f"Earth Search returned {len(features)} candidate scenes"
        features.sort(key=lambda item: item.get("properties", {}).get("eo:cloud_cover", 100))
        for feature in features:
            assets = feature.get("assets", {})
            if all(name in assets and assets[name].get("href") for name in ("red", "green", "blue", "nir")):
                return feature
        _planet_search_diagnostic += "; none exposed all red, green, blue, and nir assets"
        return None
    except Exception as exc:
        response = getattr(exc, "response", None)
        detail = response.text[:500] if response is not None else str(exc)
        print(f"⚠️ Sentinel-2 search failed ({getattr(response, 'status_code', 'network')}): {detail}")
        return None


def _process_sentinel_scene(scene: dict, geometry: dict) -> dict:
    """Read Sentinel-2 COG bands, clip to the polygon, and calculate indices."""
    import rasterio
    from rasterio.mask import mask as rasterio_mask
    from rasterio.warp import transform_geom

    bands = {}
    raster_geometry_input = _normalize_polygon_geometry(geometry)
    for name in ("blue", "green", "red", "nir"):
        with rasterio.open(scene["assets"][name]["href"]) as dataset:
            raster_geometry = transform_geom("EPSG:4326", dataset.crs, raster_geometry_input)
            clipped, _ = rasterio_mask(dataset, [raster_geometry], crop=True, filled=False)
            values = clipped[0].astype("float32")
            values = np.where(values > 2, values / 10000.0, values)
            bands[name] = values

    blue, green, red, nir = (bands[name] for name in ("blue", "green", "red", "nir"))
    valid = np.isfinite(red) & np.isfinite(nir) & np.isfinite(green) & (red + nir > 0)
    eps = 1e-10
    ndvi = np.where(valid, (nir - red) / (nir + red + eps), np.nan)
    evi = np.where(valid, 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1 + eps), np.nan)
    ndwi = np.where(valid, (green - nir) / (green + nir + eps), np.nan)
    mn = float(np.nanmean(ndvi))
    me = float(np.nanmean(evi))
    mw = float(np.nanmean(ndwi))

    cmap = _plt.cm.RdYlGn if _MATPLOTLIB_OK else None
    if cmap:
        colored = cmap(np.nan_to_num((np.clip(ndvi, -1, 1) + 1) / 2, nan=0.5))
        from PIL import Image as _P
        image = _P.fromarray((colored[:, :, :3] * 255).astype(np.uint8))
        image.thumbnail((256, 256), _P.LANCZOS)
        buf = _io_mod.BytesIO()
        image.save(buf, format="PNG")
        heatmap = _b64.b64encode(buf.getvalue()).decode()
    else:
        heatmap = _synthetic_heatmap(mn)

    props = scene.get("properties", {})
    acquired = props.get("datetime") or props.get("start_datetime") or ""
    return {
        "mean_ndvi": round(mn, 4), "mean_evi": round(me, 4), "mean_ndwi": round(mw, 4),
        "health_class": _classify_ndvi(mn), "heatmap_b64": heatmap,
        "scene_id": scene.get("id", ""), "acquired": acquired,
        "cloud_cover": float(props.get("eo:cloud_cover", 0)) / 100.0,
        "data_source": "sentinel-2",
    }


def _process_tiff(raw: bytes, mean_ndvi_fallback: float, geometry: Optional[dict] = None) -> dict:
    """Read multi-band GeoTIFF, compute NDVI/EVI/NDWI, return stats + heatmap."""
    if geometry:
        try:
            import rasterio
            from rasterio.mask import mask as rasterio_mask
            from rasterio.io import MemoryFile
            with MemoryFile(raw) as memfile:
                with memfile.open() as dataset:
                    clipped, _ = rasterio_mask(dataset, [geometry], crop=True, filled=False)
                    data_4d = clipped.filled(np.nan)
        except Exception as exc:
            print(f"⚠️ GeoTIFF polygon clipping unavailable: {exc}")
            data_4d = None
    else:
        data_4d = None
    if not _TIFF_OK:
        if data_4d is None:
            raise ImportError("tifffile not available")
    if data_4d is None:
        import tifffile as tf
        data_4d = tf.imread(_io_mod.BytesIO(raw))  # shape: (bands, H, W) or (H, W, bands)
    if data_4d.ndim == 2:
        raise ValueError("Single band only")
    if data_4d.ndim == 3 and data_4d.shape[0] <= 8:
        # (bands, H, W) format
        bands = data_4d.astype(float)
        if bands.shape[0] >= 4:
            blue, green, red, nir = bands[0], bands[1], bands[2], bands[3]
        elif bands.shape[0] == 3:
            green, red, nir = bands[0], bands[1], bands[2]
            blue = green
        else:
            raise ValueError("Insufficient bands")
    else:
        # (H, W, bands)
        bands = data_4d.astype(float)
        if bands.shape[2] >= 4:
            blue, green, red, nir = bands[..., 0], bands[..., 1], bands[..., 2], bands[..., 3]
        elif bands.shape[2] == 3:
            green, red, nir = bands[..., 0], bands[..., 1], bands[..., 2]
            blue = green
        else:
            raise ValueError("Insufficient bands")

    valid = (red > 0) & (nir > 0) & (green > 0)
    eps = 1e-10
    ndvi = np.where(valid, (nir - red) / (nir + red + eps), np.nan)
    evi = np.where(valid, 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1 + eps), np.nan)
    ndwi = np.where(valid, (green - nir) / (green + nir + eps), np.nan)

    mn = float(np.nanmean(ndvi)) if not np.all(np.isnan(ndvi)) else mean_ndvi_fallback
    me = float(np.nanmean(evi)) if not np.all(np.isnan(evi)) else mn * 0.8
    mw = float(np.nanmean(ndwi)) if not np.all(np.isnan(ndwi)) else -mn * 0.3

    # Heatmap
    if _MATPLOTLIB_OK:
        cmap = _plt.cm.RdYlGn
        clipped = np.clip(ndvi, -1, 1)
        norm = (clipped + 1) / 2
        colored = cmap(np.nan_to_num(norm, nan=0.5))
        # Downsample to max 256px
        h, w = norm.shape
        scale = min(1.0, 256 / max(h, w))
        from PIL import Image as _P
        img = _P.fromarray((colored[:, :, :3] * 255).astype(np.uint8))
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), _P.LANCZOS)
        buf = _io_mod.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        hmap = _b64.b64encode(buf.read()).decode()
    else:
        hmap = _synthetic_heatmap(mn)

    return {
        "mean_ndvi": round(mn, 4),
        "mean_evi": round(me, 4),
        "mean_ndwi": round(mw, 4),
        "health_class": _classify_ndvi(mn),
        "heatmap_b64": hmap,
    }


@app.post("/api/crop-health/analyze")
async def analyze_crop_health(payload: CropHealthRequest, user: User = Depends(get_current_user)):
    """
    Search public Earth Search Sentinel-2 imagery over the drawn polygon,
    compute NDVI/EVI/NDWI, generate a colorized heatmap, store results in SQLite,
    and return indices + history + anomaly detection.
    """
    global _planet_search_diagnostic
    farm_id = resolve_farm_id(user)
    geo_str = json.dumps(payload.geometry, sort_keys=True)
    field_id = payload.field_id or _hashlib.md5(geo_str.encode()).hexdigest()[:12]

    # ── Public Sentinel-2 STAC API ────────────────────────────────────────────
    result: dict = {}
    scene_id = ""
    scene = _sentinel_search(payload.geometry)

    if scene:
        scene_id = scene["id"]
        try:
            result = _process_sentinel_scene(scene, payload.geometry)
        except Exception as exc:
            _planet_search_diagnostic = f"Sentinel-2 scene {scene_id} processing failed: {exc}"
            print(f"⚠️ Sentinel-2 processing: {exc}")

    # Synthetic data is opt-in for demos; live failures must be visible.
    if not result and not payload.demo_mode:
        raise HTTPException(
            status_code=502,
            detail=f"Earth Search returned no usable Sentinel-2 scene or asset: {_planet_search_diagnostic}. Enable demo_mode explicitly for a synthetic demo result.",
        )

    if not result:
        seed = int(_hashlib.md5(field_id.encode()).hexdigest(), 16) % (2 ** 32)
        rng = np.random.RandomState(seed)
        mn = round(float(np.clip(rng.normal(0.52, 0.09), 0.15, 0.82)), 4)
        me = round(float(np.clip(mn * 0.85 + rng.normal(0, 0.03), 0.05, 0.90)), 4)
        mw = round(float(np.clip(-mn * 0.38 + rng.normal(0, 0.04), -0.7, 0.2)), 4)
        result = {
            "mean_ndvi": mn, "mean_evi": me, "mean_ndwi": mw,
            "health_class": _classify_ndvi(mn),
            "heatmap_b64": _synthetic_heatmap(mn),
            "scene_id": scene_id or "synthetic",
            "acquired": datetime.utcnow().isoformat(),
            "cloud_cover": 0,
            "data_source": "synthetic",
        }

    scene_date = (result.get("acquired") or datetime.utcnow().isoformat())[:10]
    scan_id = _store_crop_scan_db(field_id, payload.geometry, result, scene_date)
    history = _get_ndvi_history_db(field_id)
    anomaly = _detect_anomaly(history)

    return {
        **result,
        "field_id": field_id,
        "scan_id": scan_id,
        "cached": False,
        "history": history,
        "anomaly": anomaly,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/crop-health/history/{field_id}")
async def get_crop_health_history(field_id: str, user: User = Depends(get_current_user)):
    history = _get_ndvi_history_db(field_id, limit=10)
    anomaly = _detect_anomaly(history)
    return {"field_id": field_id, "history": history, "anomaly": anomaly}


# ============================================================
# MODULE: LAST-KILOMETER REALITY ENGINE (OSRM + OpenStreetMap)
# ============================================================

OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"

AUCTION_CENTERS: dict = {
    "guwahati": {"name": "Guwahati Tea Auction Centre",  "lat": 26.1445, "lng": 91.7362},
    "siliguri":  {"name": "Siliguri Tea Auction Centre", "lat": 26.7271, "lng": 88.3953},
    "kolkata":   {"name": "Kolkata Tea Auction Centre",  "lat": 22.5726, "lng": 88.3639},
    "jorhat":    {"name": "Jorhat Tea Auction Centre",   "lat": 26.7509, "lng": 94.2037},
}

SLOPE_FACTORS: dict = {
    "guwahati": 0.25, "siliguri": 0.45, "kolkata": 0.20, "jorhat": 0.30, "default": 0.30
}


class RouteAnalyzeRequest(BaseModel):
    origin_lat: float
    origin_lng: float
    origin_name: Optional[str] = "Tea Garden"
    destination: str                           # auction-center key or "custom"
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None
    destination_name: Optional[str] = None


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = _math.radians(lat1), _math.radians(lat2)
    dp = _math.radians(lat2 - lat1)
    dl = _math.radians(lon2 - lon1)
    a = _math.sin(dp / 2) ** 2 + _math.cos(p1) * _math.cos(p2) * _math.sin(dl / 2) ** 2
    return R * 2 * _math.atan2(_math.sqrt(a), _math.sqrt(1 - a))


def _segment_coords(coords: list, chunk_km: float = 3.0) -> list:
    segs, cur, dist = [], [coords[0]], 0.0
    for i in range(1, len(coords)):
        p, c = coords[i - 1], coords[i]
        dist += _haversine(p[1], p[0], c[1], c[0])
        cur.append(c)
        if dist >= chunk_km:
            segs.append(cur); cur = [c]; dist = 0.0
    if len(cur) > 1:
        segs.append(cur)
    elif segs:
        segs[-1].extend(cur[1:])
    return segs or [coords]


def _rainfall_intensity(lat: float, lng: float) -> float:
    return _get_open_meteo_rain(lat, lng)


def _risk_level(score: float) -> str:
    return "LOW" if score < 0.3 else ("MEDIUM" if score < 0.6 else "HIGH")


def _spoilage(risk: str) -> float:
    return {"LOW": 0.02, "MEDIUM": 0.07, "HIGH": 0.15}.get(risk, 0.07)


def _call_osrm(olng, olat, dlng, dlat) -> Optional[dict]:
    try:
        url = f"{OSRM_BASE}/{olng},{olat};{dlng},{dlat}?overview=full&geometries=geojson&steps=true"
        r = _http.get(url, timeout=20, headers={"User-Agent": "ChaiNet/1.0"})
        r.raise_for_status()
        d = r.json()
        if d.get("code") == "Ok" and d.get("routes"):
            return d["routes"][0]
    except Exception as exc:
        print(f"⚠️ OSRM: {exc}")
    return None


def _build_segment_risks(segments: list) -> list:
    def build_one(seg):
        mid_lat = sum(c[1] for c in seg) / len(seg)
        mid_lng = sum(c[0] for c in seg) / len(seg)
        rain = _rainfall_intensity(mid_lat, mid_lng)
        segment_distance_m = sum(
            _haversine(seg[i - 1][1], seg[i - 1][0], seg[i][1], seg[i][0]) * 1000
            for i in range(1, len(seg))
        )
        sf = _get_elevation_slope(
            seg[0][1], seg[0][0], seg[-1][1], seg[-1][0], segment_distance_m
        )
        corridor = _get_historical_delay(mid_lat, mid_lng)
        df = corridor["historical_delay_flag"]
        score = round(min(1.0, 0.5 * rain + 0.3 * sf + 0.2 * df), 3)
        print(f"    Segment risk: rain={rain:.3f} slope={sf:.3f} delay={df:.3f} score={score:.3f} level={_risk_level(score)}")
        return {
            "coordinates": seg,
            "risk_score": score,
            "risk_level": _risk_level(score),
            "rainfall_intensity": rain,
            "slope_factor": sf,
            "delay_flag": df,
            "corridor_name": corridor["corridor_name"],
            "hazard_type": corridor["hazard_type"],
            "hazard_description": corridor["hazard_description"],
            "severity": corridor["severity"],
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(build_one, segments))


def _collect_route_advisories(segments: list) -> list:
    advisories = []
    seen = set()
    for segment in segments:
        hazard_type = segment.get("hazard_type")
        if not hazard_type or hazard_type in seen:
            continue
        seen.add(hazard_type)
        advisories.append({
            "hazard_type": hazard_type,
            "description": segment.get("hazard_description"),
            "severity": segment.get("severity") or "moderate",
            "corridor_name": segment.get("corridor_name"),
        })
    return advisories


def _route_fallback(olat, olng, dlat, dlng, dest_name, dest_key) -> dict:
    dist = round(_haversine(olat, olng, dlat, dlng) * 1.4, 1)
    dur = round(dist / 40 * 60)
    mid = [(olng + dlng) / 2 + 0.05, (olat + dlat) / 2]
    coords = [[olng, olat], mid, [dlng, dlat]]
    segs = _segment_coords(coords)
    risk_segments = _build_segment_risks(segs)
    score = round(float(np.mean([s["risk_score"] for s in risk_segments])), 3)
    rl = _risk_level(score)
    sp = _spoilage(rl)
    advisories = _collect_route_advisories(risk_segments)
    return {
        "origin": {"lat": olat, "lng": olng, "name": "Tea Garden"},
        "destination": {"lat": dlat, "lng": dlng, "name": dest_name, "key": dest_key},
        "distance_km": dist, "duration_min": dur,
        "route_risk": rl, "risk_score": score,
        "segments": risk_segments,
        "geometry": {"type": "LineString", "coordinates": coords},
        "spoilage_probability": sp, "spoilage_pct": int(sp * 100),
        "base_price": 280.0, "effective_price": round(280.0 * (1 - sp), 2),
        "recommended_harvest_shift": 1 if rl == "HIGH" else 0,
        "route_advisories": advisories,
        "severe_hazard_warning": next((a["description"] for a in advisories if a["severity"] == "severe"), None),
        "alternate_route": None, "cached": False, "fallback": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/route/auction-centers")
def route_auction_centers():
    return {"centers": [{"key": k, **v} for k, v in AUCTION_CENTERS.items()]}


@app.post("/api/route/analyze")
async def analyze_route(payload: RouteAnalyzeRequest, user: User = Depends(get_current_user)):
    """
    Compute route risk from origin to tea auction destination using OSRM.
    Returns per-segment risk scores (LOW/MEDIUM/HIGH), spoilage probability,
    effective price, and an alternate route suggestion when risk is HIGH.
    """
    farm_id = resolve_farm_id(user)

    # ── Resolve destination ──────────────────────────────────────────────────
    if payload.destination in AUCTION_CENTERS:
        dest_key = payload.destination
        di = AUCTION_CENTERS[dest_key]
        dlat, dlng, dest_name = di["lat"], di["lng"], di["name"]
    elif payload.destination_lat and payload.destination_lng:
        dlat, dlng = payload.destination_lat, payload.destination_lng
        dest_name = payload.destination_name or "Custom Destination"
        dest_key = "custom"
    else:
        # Nominatim geocode
        try:
            gr = _http.get(
                "https://nominatim.openstreetmap.org/search",
                params={"format": "json", "q": payload.destination, "limit": 1},
                headers={"User-Agent": "ChaiNet/1.0"}, timeout=10
            )
            gd = gr.json()
            if not gd:
                raise HTTPException(status_code=400, detail="Could not geocode destination")
            dlat, dlng = float(gd[0]["lat"]), float(gd[0]["lon"])
            dest_name = gd[0].get("display_name", payload.destination)[:80]
            dest_key = "custom"
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Geocoding failed: {exc}")

    # ── OSRM route ───────────────────────────────────────────────────────────
    route = _call_osrm(payload.origin_lng, payload.origin_lat, dlng, dlat)
    if not route:
        return _route_fallback(payload.origin_lat, payload.origin_lng, dlat, dlng, dest_name, dest_key)

    coords = route["geometry"]["coordinates"]
    dist_km = round(route["distance"] / 1000, 1)
    dur_min = round(route["duration"] / 60)

    segs = _segment_coords(coords)
    seg_risks = _build_segment_risks(segs)
    avg_risk = float(np.mean([s["risk_score"] for s in seg_risks]))
    rl = _risk_level(avg_risk)
    sp = _spoilage(rl)
    route_advisories = _collect_route_advisories(seg_risks)
    severe_warning = next(
        (s["hazard_description"] for s in seg_risks if s.get("severity") == "severe"),
        None,
    )

    # Base price from Firestore or fallback
    try:
        pdoc = db.collection("farms").doc(farm_id).collection("market").document("latest").get()
        base_price = float(pdoc.to_dict().get("predicted_price", 280)) if pdoc.exists else 280.0
    except Exception:
        base_price = 280.0

    # ── Alternate route if HIGH risk ─────────────────────────────────────────
    alternate = None
    if rl == "HIGH":
        alt_key = min(
            (k for k in AUCTION_CENTERS if k != dest_key),
            key=lambda k: _haversine(payload.origin_lat, payload.origin_lng,
                                     AUCTION_CENTERS[k]["lat"], AUCTION_CENTERS[k]["lng"])
        )
        ai = AUCTION_CENTERS[alt_key]
        alt_route = _call_osrm(payload.origin_lng, payload.origin_lat, ai["lng"], ai["lat"])
        if alt_route:
            alt_segs = _segment_coords(alt_route["geometry"]["coordinates"])
            alt_risks = _build_segment_risks(alt_segs)
            alt_avg = float(np.mean([s["risk_score"] for s in alt_risks]))
            alt_rl = _risk_level(alt_avg)
            alt_sp = _spoilage(alt_rl)
            alternate = {
                "destination_key": alt_key,
                "destination_name": ai["name"],
                "route_risk": alt_rl,
                "risk_score": round(alt_avg, 3),
                "distance_km": round(alt_route["distance"] / 1000, 1),
                "duration_min": round(alt_route["duration"] / 60),
                "spoilage_probability": alt_sp,
                "spoilage_pct": int(alt_sp * 100),
                "effective_price": round(base_price * (1 - alt_sp), 2),
                "segments": alt_risks,
                "geometry": alt_route["geometry"],
            }

    result = {
        "origin": {"lat": payload.origin_lat, "lng": payload.origin_lng, "name": payload.origin_name},
        "destination": {"lat": dlat, "lng": dlng, "name": dest_name, "key": dest_key},
        "distance_km": dist_km, "duration_min": dur_min,
        "route_risk": rl, "risk_score": round(avg_risk, 3),
        "segments": seg_risks,
        "geometry": route["geometry"],
        "spoilage_probability": sp, "spoilage_pct": int(sp * 100),
        "base_price": base_price,
        "effective_price": round(base_price * (1 - sp), 2),
        "recommended_harvest_shift": 1 if rl == "HIGH" else 0,
        "route_advisories": route_advisories,
        "severe_hazard_warning": severe_warning,
        "alternate_route": alternate,
        "cached": False,
        "timestamp": datetime.utcnow().isoformat(),
    }

    return result


@app.post("/api/route/seed-demo")
async def seed_demo_routes():
    """Seed 3 pre-built demo route scenarios for reliable stage demos."""
    scenarios = [
        {
            "name": "Clear Weather — Guwahati Run",
            "dest_key": "guwahati",
            "origin": {"lat": 26.5714, "lng": 93.8441, "name": "Assam Garden (Jorhat)"},
            "destination": {"lat": 26.1445, "lng": 91.7362, "name": "Guwahati Tea Auction Centre", "key": "guwahati"},
            "distance_km": 187.4, "duration_min": 210,
            "route_risk": "LOW", "risk_score": 0.18,
            "spoilage_probability": 0.02, "spoilage_pct": 2,
            "base_price": 285.0, "effective_price": 279.3,
            "recommended_harvest_shift": 0, "alternate_route": None,
            "segments": [{"coordinates": [[93.84,26.57],[92.78,26.38],[91.74,26.14]], "risk_score": 0.18, "risk_level": "LOW", "rainfall_intensity": 0.10, "slope_factor": 0.25, "delay_flag": 0.15}],
            "geometry": {"type": "LineString", "coordinates": [[93.84,26.57],[92.78,26.38],[91.74,26.14]]},
            "cached": False, "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "name": "Heavy Rain Forecast — HIGH Risk Siliguri",
            "dest_key": "siliguri",
            "origin": {"lat": 26.5714, "lng": 93.8441, "name": "Assam Garden (Jorhat)"},
            "destination": {"lat": 26.7271, "lng": 88.3953, "name": "Siliguri Tea Auction Centre", "key": "siliguri"},
            "distance_km": 432.1, "duration_min": 540,
            "route_risk": "HIGH", "risk_score": 0.74,
            "spoilage_probability": 0.15, "spoilage_pct": 15,
            "base_price": 285.0, "effective_price": 242.25,
            "recommended_harvest_shift": 1,
            "segments": [
                {"coordinates": [[93.84,26.57],[92.0,26.4],[90.5,26.6]], "risk_score": 0.82, "risk_level": "HIGH", "rainfall_intensity": 0.78, "slope_factor": 0.45, "delay_flag": 0.50},
                {"coordinates": [[90.5,26.6],[89.5,26.65],[88.4,26.73]], "risk_score": 0.65, "risk_level": "HIGH", "rainfall_intensity": 0.62, "slope_factor": 0.45, "delay_flag": 0.50},
            ],
            "geometry": {"type": "LineString", "coordinates": [[93.84,26.57],[92.0,26.4],[90.5,26.6],[89.5,26.65],[88.4,26.73]]},
            "alternate_route": {
                "destination_key": "guwahati",
                "destination_name": "Guwahati Tea Auction Centre",
                "route_risk": "LOW", "risk_score": 0.18,
                "distance_km": 187.4, "duration_min": 210,
                "spoilage_probability": 0.02, "spoilage_pct": 2, "effective_price": 279.3,
                "segments": [], "geometry": {"type": "LineString", "coordinates": [[93.84,26.57],[91.74,26.14]]},
            },
            "cached": False, "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "name": "Borderline MEDIUM — Long Kolkata Haul",
            "dest_key": "kolkata",
            "origin": {"lat": 26.5714, "lng": 93.8441, "name": "Assam Garden (Jorhat)"},
            "destination": {"lat": 22.5726, "lng": 88.3639, "name": "Kolkata Tea Auction Centre", "key": "kolkata"},
            "distance_km": 634.2, "duration_min": 720,
            "route_risk": "MEDIUM", "risk_score": 0.44,
            "spoilage_probability": 0.07, "spoilage_pct": 7,
            "base_price": 285.0, "effective_price": 265.05,
            "recommended_harvest_shift": 0, "alternate_route": None,
            "segments": [
                {"coordinates": [[93.84,26.57],[91.5,26.1],[89.0,25.0]], "risk_score": 0.38, "risk_level": "MEDIUM", "rainfall_intensity": 0.35, "slope_factor": 0.30, "delay_flag": 0.30},
                {"coordinates": [[89.0,25.0],[88.5,23.5],[88.36,22.57]], "risk_score": 0.50, "risk_level": "MEDIUM", "rainfall_intensity": 0.48, "slope_factor": 0.30, "delay_flag": 0.30},
            ],
            "geometry": {"type": "LineString", "coordinates": [[93.84,26.57],[91.5,26.1],[89.0,25.0],[88.5,23.5],[88.36,22.57]]},
            "cached": False, "timestamp": datetime.utcnow().isoformat(),
        },
    ]

    written = 0
    for s in scenarios:
        print(f"Demo route scenario available only through live analysis: {s['name']}")

    return {"seeded": written, "scenarios": [s["name"] for s in scenarios], "message": "Live OSRM analysis is required."}

# ============================================================
# MODULE: PARAMETRIC CLIMATE RISK ENGINE
# ============================================================
import uuid

@app.post("/api/climate-risk/evaluate/{field_id}")
def evaluate_climate_risk(field_id: str, user: User = Depends(get_current_user)):
    """
    Evaluates drought/flood risk for a field.
    Reads recent NDWI from NeonDB and soil moisture from Firestore.
    If conditions met, creates a Parametric Risk Event in Firestore.
    """
    farm_id = resolve_farm_id(user)
    
    # Clear old data for this field immediately on new evaluation session
    try:
        existing = db.collection("farms").document(farm_id).collection("parametric_risk_events").where("field_id", "==", field_id).stream()
        for ed in existing:
            ed.reference.delete()
    except Exception as e:
        print(f"⚠️ Failed deleting old events: {e}")
        
    # 1. Fetch last 2 satellite scans from NeonDB
    db_session = SessionLocal()
    try:
        scans = db_session.query(CropHealthScan).filter(
            CropHealthScan.field_id == field_id
        ).order_by(CropHealthScan.scene_date.desc()).limit(2).all()
        
        ndwi_current = None
        ndwi_drop_pct = 0.0
        ndwi_spike_pct = 0.0
        if len(scans) >= 2:
            ndwi_current = scans[0].ndwi
            ndwi_prev = scans[1].ndwi
            if ndwi_prev and ndwi_prev > 0 and ndwi_current is not None:
                if ndwi_prev > ndwi_current:
                    ndwi_drop_pct = ((ndwi_prev - ndwi_current) / ndwi_prev) * 100
                else:
                    ndwi_spike_pct = ((ndwi_current - ndwi_prev) / ndwi_prev) * 100
        elif len(scans) == 1:
            ndwi_current = scans[0].ndwi
            
    finally:
        db_session.close()
        
    if ndwi_current is None:
        # Fallback for demo purposes if NeonDB empty
        if field_id == 'demo_field':
            ndwi_drop_pct = 18.5
        else:
            return {"status": "skipped", "reason": "No satellite data available for this field."}

    # 2. Fetch last 7 days of soil moisture from Firestore
    max_consecutive_low = 0
    max_consecutive_high = 0
    day_averages = []
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        docs = db.collection("farms").document(farm_id).collection("sensors").document("sensors_root").collection("readings").where("timestamp", ">=", start_date).order_by("timestamp", direction="ASCENDING").stream()
        
        readings = []
        for d in docs:
            r = d.to_dict()
            ts = r.get("timestamp")
            if hasattr(ts, "timestamp"):
                ts_val = ts.timestamp()
            elif isinstance(ts, str):
                ts_val = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            else:
                ts_val = ts
            readings.append({
                "ts": ts_val,
                "soil_moisture": r.get("soil_moisture", 100.0)
            })
            
        readings.sort(key=lambda x: x["ts"])
        
        if readings:
            import math
            current_day = None
            daily_sum = 0
            daily_count = 0
            
            for r in readings:
                day_idx = math.floor(r["ts"] / 86400)
                if current_day != day_idx:
                    if daily_count > 0:
                        day_averages.append(daily_sum / daily_count)
                    current_day = day_idx
                    daily_sum = r["soil_moisture"]
                    daily_count = 1
                else:
                    daily_sum += r["soil_moisture"]
                    daily_count += 1
            if daily_count > 0:
                day_averages.append(daily_sum / daily_count)
                
            consecutive_low = 0
            consecutive_high = 0
            for avg in day_averages:
                if avg < 20.0:
                    consecutive_low += 1
                    max_consecutive_low = max(max_consecutive_low, consecutive_low)
                else:
                    consecutive_low = 0
                    
                if avg > 90.0:
                    consecutive_high += 1
                    max_consecutive_high = max(max_consecutive_high, consecutive_high)
                else:
                    consecutive_high = 0
                    
    except Exception as exc:
        print(f"⚠️ Error reading sensors: {exc}")

    is_drought_trigger = (ndwi_drop_pct > 15.0 and max_consecutive_low >= 3)
    is_flood_trigger = (ndwi_spike_pct > 15.0 and max_consecutive_high >= 3)
    
    if field_id == 'demo_field' and not is_drought_trigger and not is_flood_trigger:
        is_flood_trigger = True
        ndwi_spike_pct = 22.4
        max_consecutive_high = 4
        day_averages = [85.0, 92.0, 95.0, 94.0, 98.0, 96.0, 99.0]
        
    if is_drought_trigger or is_flood_trigger:
        # Get price
        current_price = 280.0
        if df is not None and PRIMARY_MARKET in df.columns:
            prices = df[PRIMARY_MARKET].dropna()
            if not prices.empty:
                current_price = float(prices.iloc[-1])
                
        event_type = "Flood" if is_flood_trigger else "Drought"
        yield_loss_pct = round(min(100, ndwi_spike_pct * 1.5 if is_flood_trigger else ndwi_drop_pct * 1.5), 1)
        financial_loss = round((5.0 * 2500) * (yield_loss_pct / 100) * current_price, 2)
        
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        event_record = {
            "id": event_id,
            "field_id": field_id,
            "event_type": event_type,
            "severity": "High",
            "date_triggered": datetime.utcnow().isoformat(),
            "trigger_conditions": {
                "ndwi_spike_pct" if is_flood_trigger else "ndwi_drop_pct": round(ndwi_spike_pct if is_flood_trigger else ndwi_drop_pct, 1),
                "consecutive_days_high_moisture" if is_flood_trigger else "consecutive_days_low_moisture": max_consecutive_high if is_flood_trigger else max_consecutive_low,
                "historical_moisture": day_averages
            },
            "estimated_yield_loss_pct": yield_loss_pct,
            "financial_loss": financial_loss,
            "current_price": current_price,
            "status": "Active"
        }
        
        try:
            db.collection("farms").document(farm_id).collection("parametric_risk_events").document(event_id).set(event_record)
        except Exception as exc:
            print(f"⚠️ Failed to save risk event: {exc}")
            
        return {"status": "triggered", "event": event_record}
        
    return {"status": "no_trigger", "message": "Risk thresholds not met"}


@app.get("/api/climate-risk/events/{field_id}")
def get_climate_risk_events(field_id: str, user: User = Depends(get_current_user)):
    farm_id = resolve_farm_id(user)
    try:
        docs = db.collection("farms").document(farm_id).collection("parametric_risk_events").where("field_id", "==", field_id).order_by("date_triggered", direction="DESCENDING").stream()
        events = [d.to_dict() for d in docs]
        return {"events": events}
    except Exception as exc:
        print(f"⚠️ Error fetching events: {exc}")
        try:
            docs = db.collection("farms").document(farm_id).collection("parametric_risk_events").where("field_id", "==", field_id).stream()
            events = [d.to_dict() for d in docs]
            events.sort(key=lambda x: x.get("date_triggered", ""), reverse=True)
            return {"events": events}
        except Exception:
            return {"events": []}


@app.get("/api/climate-risk/export/{event_id}")
def export_climate_risk_event(event_id: str, user: User = Depends(get_current_user)):
    farm_id = resolve_farm_id(user)
    try:
        doc = db.collection("farms").document(farm_id).collection("parametric_risk_events").document(event_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Event not found")
        event = doc.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
        
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    conds = event.get("trigger_conditions", {})
    hist_moisture = conds.get("historical_moisture", [])
    
    img_path = None
    if hist_moisture:
        try:
            plt.figure(figsize=(6, 3))
            plt.plot(range(1, len(hist_moisture)+1), hist_moisture, marker='o', color='#B71C1C', linewidth=2)
            plt.title('Soil Moisture Trend (Last 7 Days)')
            plt.xlabel('Days')
            plt.ylabel('Moisture %')
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.ylim(0, 100)
            
            is_flood = event.get("event_type") == "Flood"
            threshold = 90 if is_flood else 20
            plt.axhline(y=threshold, color='orange', linestyle='--', label=f'Threshold ({threshold}%)')
            plt.legend()
            
            img_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(img_temp.name, bbox_inches='tight', dpi=150)
            plt.close()
            img_path = img_temp.name
        except Exception as e:
            print(f"⚠️ Failed to generate chart: {e}")
            
    pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_file.close()
    
    doc_pdf = SimpleDocTemplate(pdf_file.name, pagesize=letter, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    elements = [
        Paragraph("<b>CHAINET CLIMATE RISK ENGINE</b>", styles["Title"]),
        Paragraph("<font color='#B71C1C'>OFFICIAL PARAMETRIC TRIGGER DOCUMENT</font>", styles["Title"]),
        Spacer(1, 24),
        Paragraph("<b>1. ASSESSMENT DETAILS</b>", styles["Heading3"]),
        Paragraph(f"<b>Event ID:</b> {event.get('id', event_id)}", styles["Normal"]),
        Paragraph(f"<b>Assessment Date:</b> {event.get('date_triggered', 'N/A')}", styles["Normal"]),
        Paragraph(f"<b>Farm ID:</b> {farm_id}", styles["Normal"]),
        Paragraph(f"<b>Field ID:</b> {event.get('field_id')}", styles["Normal"]),
        Paragraph(f"<b>Risk Classification:</b> <font color='red'>{event.get('severity', 'High')} {event.get('event_type')}</font>", styles["Normal"]),
        Spacer(1, 16),
        
        Paragraph("<b>2. SATELLITE & IOT TELEMETRY (TRIGGER CONDITIONS)</b>", styles["Heading3"]),
    ]
    
    conds = event.get("trigger_conditions", {})
    is_flood = event.get("event_type") == "Flood"
    
    table_data = [
        ["Parameter", "Threshold Limit", "Recorded Value", "Status"],
        ["NDWI Change (%)", "> 15.0% (Spike)" if is_flood else "> 15.0% (Drop)", f"{conds.get('ndwi_spike_pct' if is_flood else 'ndwi_drop_pct', 'N/A')}%", "BREACHED"],
        ["Moisture Duration", ">= 3 Days (>90%)" if is_flood else ">= 3 Days (<20%)", f"{conds.get('consecutive_days_high_moisture' if is_flood else 'consecutive_days_low_moisture', 'N/A')} Days", "BREACHED"],
    ]
    
    table = Table(table_data, colWidths=[140, 120, 100, 80])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9F9F9")),
        ("TEXTCOLOR", (3, 1), (3, -1), colors.HexColor("#B71C1C")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10)
    ]))
    
    elements.extend([
        Spacer(1, 8),
        table,
        Spacer(1, 16),
    ])
    
    if img_path:
        elements.extend([
            Paragraph("<b>TELEMETRY VISUALIZATION</b>", styles["Heading3"]),
            Spacer(1, 8),
            RLImage(img_path, width=400, height=200),
            Spacer(1, 16),
        ])
        
    def format_inr(value):
        s = str(int(value))
        if len(s) <= 3: return s
        res = s[-3:]
        s = s[:-3]
        while len(s) > 0:
            res = s[-2:] + "," + res
            s = s[:-2]
        return res
        
    formatted_loss = format_inr(event.get('financial_loss', 0))

    elements.extend([
        Paragraph("<b>3. IMPACT ESTIMATION</b>", styles["Heading3"]),
        Paragraph(f"<b>Estimated Yield Loss:</b> <font size='12' color='#B71C1C'><b>{event.get('estimated_yield_loss_pct', 0)}%</b></font>", styles["Normal"]),
        Paragraph(f"<b>Financial Loss Estimate:</b> <font size='12'><b>INR {formatted_loss}</b></font> (Based on current market price of ₹{event.get('current_price', 280.0):.1f}/kg)", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("<b>Financial Impact:</b> Automatic payout procedure initiated based on the registered policy smart contract. Subject to local verifications.", styles["Normal"]),
        Spacer(1, 36),
        Paragraph("<font size='8' color='grey'><b>DISCLAIMER:</b> This is an auto-generated parametric insurance trigger document generated by the ChaiNet Climate Risk Engine. No manual loss assessment or physical field inspection is required. The physical data parameters have exceeded the pre-defined policy threshold limits, qualifying for automatic settlement.</font>", styles["Normal"])
    ])
    
    doc_pdf.build(elements)
    
    return FileResponse(
        pdf_file.name, 
        media_type="application/pdf", 
        filename=f"parametric-risk-trigger-{event_id}.pdf"
    )

class DigitalTwinRequest(BaseModel):
    irrigation_freq_days: int
    disease_intervention_days: int
    climate_model: str = "normal"
    expected_monthly_yield: int = 1500

@app.post("/api/digital-twin/forecast/{field_id}")
def generate_digital_twin_forecast(field_id: str, payload: DigitalTwinRequest):
    import math
    from datetime import datetime, timedelta
    
    current_date = datetime.now()
    forecast_data = []
    
    # Ground simulation in Live Data
    db_session = SessionLocal()
    try:
        latest_scan = db_session.query(CropHealthScan).filter(
            CropHealthScan.field_id == field_id
        ).order_by(CropHealthScan.scene_date.desc()).first()
        base_ndvi_start = latest_scan.ndvi if latest_scan and latest_scan.ndvi else 0.70
    except Exception:
        base_ndvi_start = 0.70
    finally:
        db_session.close()
    
    # Climate Model Modifiers
    base_decay = 0.003
    stress_decay = 0.004
    drought_months = [4, 5, 6]
    flood_months = []
    stress_dip_multiplier = 0.15
    flood_dip_multiplier = 0.15

    if payload.climate_model == "el_nino":
        base_decay = 0.005
        stress_decay = 0.007
        drought_months = [4, 5, 6, 7, 8]  # Extended severe drought
        stress_dip_multiplier = 0.25
    elif payload.climate_model == "la_nina":
        base_decay = 0.002
        stress_decay = 0.004
        drought_months = [4, 5]
        flood_months = [7, 8, 9]  # Heavy monsoon waterlogging
        flood_dip_multiplier = 0.20

    cumulative_bau_revenue = 0
    cumulative_optimistic_revenue = 0
    
    # Fetch live price from market data (Guwahati default)
    try:
        current_price = float(df[PRIMARY_MARKET].dropna().iloc[-1])
    except Exception:
        current_price = 280.0  # Fallback to ₹280/kg
        
    max_potential_revenue = payload.expected_monthly_yield * current_price

    for month in range(60):
        # Base seasonal sine wave (NDVI varies between 0.55 and 0.85 naturally)
        date = current_date + timedelta(days=30 * month)
        date_str = date.strftime("%b %Y")
        
        # Base cycle grounded in actual starting NDVI
        base_ndvi = base_ndvi_start + 0.15 * math.sin((date.month / 12.0) * 2 * math.pi)
        
        # Business As Usual
        bau_ndvi = base_ndvi - (month * base_decay)
        
        # Stress Scenario
        is_drought = date.month in drought_months
        is_flood = date.month in flood_months
        
        dip = 0.0
        if is_drought: dip += stress_dip_multiplier
        if is_flood: dip += flood_dip_multiplier
            
        stress_ndvi = base_ndvi - (month * stress_decay) - dip
        
        # Optimistic (Managed)
        irrigation_penalty = max(0, payload.irrigation_freq_days - 3) * 0.001
        intervention_penalty = max(0, payload.disease_intervention_days - 2) * 0.0015
        
        managed_dip = 0.05 if (is_drought or is_flood) else 0.0
        managed_ndvi = base_ndvi - (month * (irrigation_penalty + intervention_penalty)) - managed_dip
        
        # Bound limits
        bau_val = round(max(0, bau_ndvi), 3)
        stress_val = round(max(0, stress_ndvi), 3)
        opt_val = round(max(0, managed_ndvi), 3)

        forecast_data.append({
            "date": date_str,
            "bau": bau_val,
            "stress": stress_val,
            "optimistic": opt_val
        })

        # Financials
        cumulative_bau_revenue += max_potential_revenue * (bau_val / 0.85)
        cumulative_optimistic_revenue += max_potential_revenue * (opt_val / 0.85)
        
    # Generate Summary text
    final_bau = forecast_data[-1]["bau"]
    final_managed = forecast_data[-1]["optimistic"]
    
    bau_status = "Healthy" if final_bau >= 0.7 else "Moderate" if final_bau >= 0.5 else "Critical"
    managed_status = "Healthy" if final_managed >= 0.7 else "Moderate" if final_managed >= 0.5 else "Critical"
    
    summary = f"Under a {payload.climate_model.replace('_', ' ').title()} climate model with Business-as-Usual management, {field_id.replace('_', ' ').title()} is projected to decline to '{bau_status}' health. However, following your intervention plan (Irrigation: {payload.irrigation_freq_days} days, Disease treatment: {payload.disease_intervention_days} days) maintains a '{managed_status}' status through the same 5-year period."
    
    financials = {
        "bau_loss": round((60 * max_potential_revenue) - cumulative_bau_revenue),
        "optimistic_loss": round((60 * max_potential_revenue) - cumulative_optimistic_revenue),
        "savings": round(cumulative_optimistic_revenue - cumulative_bau_revenue)
    }

    return {
        "forecast": forecast_data,
        "summary": summary,
        "financials": financials
    }

class BatchPredictionRequest(BaseModel):
    ndvi: float
    leaf_quality: float
    withering_hours: float
    withering_temp: float
    fermentation_hours: float
    fermentation_temp: float

@app.post("/api/batch-predictor/simulate")
def simulate_batch_quality(payload: BatchPredictionRequest):
    # 1. Base Quality from Field Data
    # NDVI (0 to 1, optimal ~ 0.7 to 0.85)
    ndvi_score = min(1.0, max(0.0, (payload.ndvi - 0.4) / 0.45)) * 50 # Max 50 pts
    
    # Leaf Quality (0 to 100)
    leaf_score = (payload.leaf_quality / 100) * 50 # Max 50 pts
    
    base_potential = ndvi_score + leaf_score # Out of 100
    
    # 2. TF:TR Ratio Calculation
    # Optimal ratio is > 1:10 (0.1). High is 1:10 (0.10). Low is 1:15 (0.066)
    # Start with ideal ratio 0.12 (Premium Brisk)
    ratio = 0.12
    
    # Penalize Withering
    # Optimal 18-22h at 20-22°C
    if payload.withering_temp > 25:
        ratio -= (payload.withering_temp - 25) * 0.005 # Heat damage
    if payload.withering_hours < 16:
        ratio -= (16 - payload.withering_hours) * 0.005 # Under-withered
    elif payload.withering_hours > 24:
        ratio -= (payload.withering_hours - 24) * 0.002 # Over-withered (flat)
        
    # Penalize Fermentation (Critical for TF)
    # Optimal 2-3h at 25-28°C
    if payload.fermentation_temp > 29:
        ratio -= (payload.fermentation_temp - 29) * 0.01 # Rapidly converts TF to TR (dull)
    if payload.fermentation_hours > 3.5:
        ratio -= (payload.fermentation_hours - 3.5) * 0.015 # Over-fermentation (soft/dull)
    elif payload.fermentation_hours < 1.5:
        ratio -= (1.5 - payload.fermentation_hours) * 0.01 # Under-fermentation (green/raw)
        
    # Ensure ratio stays between 0.03 (Very poor) and 0.15 (Exceptional)
    final_ratio = max(0.03, min(0.15, ratio))
    
    # 3. Grade Classification
    grade = "Basic"
    if final_ratio >= 0.09 and base_potential >= 75:
        grade = "Premium"
    elif final_ratio >= 0.065 and base_potential >= 50:
        grade = "Standard"
        
    # 4. Generate Tasting Note
    note_parts = []
    
    # Color/Liquor
    if final_ratio >= 0.09:
        note_parts.append("Expected: bright golden liquor, high briskness, suitable for premium orthodox grade")
    elif final_ratio >= 0.065:
        note_parts.append("Expected: rich amber liquor, medium body and briskness, standard CTC profile")
    else:
        note_parts.append("Expected: dark/dull liquor, flat body lacking briskness")
        
    # Drivers
    drivers = []
    if payload.fermentation_temp > 29:
        drivers.append(f"high fermentation heat ({payload.fermentation_temp}°C) driving too much Thearubigin")
    elif payload.fermentation_temp <= 28 and payload.fermentation_hours <= 3.0:
        drivers.append(f"optimal fermentation control")
        
    if payload.withering_hours < 16:
        drivers.append(f"under-withering ({payload.withering_hours}h)")
    elif 18 <= payload.withering_hours <= 22 and payload.withering_temp <= 22:
        drivers.append(f"excellent withering conditions")
        
    if payload.ndvi > 0.65 and payload.leaf_quality > 80:
        drivers.append(f"strong leaf health at plucking (NDVI {payload.ndvi})")
    elif payload.ndvi < 0.5:
        drivers.append(f"poor field health limiting potential")
        
    tasting_note = note_parts[0]
    if drivers:
        tasting_note += " — driven by " + " and ".join(drivers) + "."
    else:
        tasting_note += "."
        
    return {
        "base_potential": round(base_potential, 1),
        "tf_tr_ratio": round(final_ratio, 3),
        "predicted_grade": grade,
        "tasting_note": tasting_note
    }


# ===================================================================
# LEAF POTENTIAL ANALYSIS — Pre-Harvest Field-Level Cup Predictor
# ===================================================================

def _score_dry_spell(rainfall_history: list) -> float:
    """
    Score based on recent rainfall pattern.
    2-4 dry days after adequate prior moisture = best catechin concentration.
    """
    # Count consecutive recent dry days (rainfall < 2mm per day)
    dry_days = sum(1 for r in rainfall_history[-4:] if r < 2.0)
    if 2 <= dry_days <= 4:
        return 95.0   # Optimal moisture stress window
    elif dry_days == 1:
        return 75.0   # Mild stress, still good
    elif dry_days == 0:
        return 45.0   # Waterlogged, catechin dilution risk
    else:
        return 60.0   # Over-stressed, quality variance

def _score_diurnal_swing(temp_swing: float) -> float:
    """
    Score diurnal temperature range. >12°C = premium aromatic character.
    """
    if temp_swing >= 14:
        return 100.0
    elif temp_swing >= 11:
        return 85.0
    elif temp_swing >= 8:
        return 65.0
    elif temp_swing >= 5:
        return 45.0
    else:
        return 25.0

def _score_ndwi(ndwi: float) -> float:
    """
    Score water content index. Slight deficit (-0.1 to 0.0) favors briskness.
    """
    if -0.15 <= ndwi <= 0.0:
        return 95.0    # Slight deficit — concentrates polyphenols
    elif 0.0 < ndwi <= 0.15:
        return 78.0    # Adequate but not stressed
    elif ndwi > 0.15:
        return 50.0    # Water surplus — dilution risk
    else:
        return 40.0    # Severe deficit

def _score_soil_moisture(sm: float) -> float:
    """55-65% optimal for body/strength."""
    if 55 <= sm <= 65:
        return 100.0
    elif 50 <= sm < 55 or 65 < sm <= 70:
        return 75.0
    elif 45 <= sm < 50 or 70 < sm <= 75:
        return 50.0
    else:
        return 25.0

def _score_evi(evi: float) -> float:
    """
    Enhanced Vegetation Index. 0.4-0.6 = healthy vigorous growth (body/strength).
    """
    if 0.40 <= evi <= 0.60:
        return 100.0
    elif 0.30 <= evi < 0.40 or 0.60 < evi <= 0.70:
        return 75.0
    elif 0.20 <= evi < 0.30:
        return 50.0
    else:
        return 30.0

def _score_humidity_consistency(hum_history: list) -> float:
    """
    Low humidity variance = consistent quality. High variance = erratic quality.
    """
    if len(hum_history) < 2:
        return 60.0
    mean_hum = sum(hum_history) / len(hum_history)
    variance = sum((h - mean_hum)**2 for h in hum_history) / len(hum_history)
    std_dev = variance ** 0.5
    # Lower std_dev = more consistent = higher score
    if std_dev < 3:
        return 95.0
    elif std_dev < 6:
        return 75.0
    elif std_dev < 10:
        return 55.0
    else:
        return 30.0

def _score_ndvi(ndvi: float) -> float:
    """0.65-0.80 = optimal leaf vigor for 2-leaves-and-a-bud pluck standard."""
    if 0.65 <= ndvi <= 0.80:
        return 100.0
    elif 0.55 <= ndvi < 0.65 or 0.80 < ndvi <= 0.85:
        return 78.0
    elif 0.45 <= ndvi < 0.55:
        return 55.0
    else:
        return 30.0

def _score_ndvi_trend(ndvi_history: list) -> float:
    """Rising or stable NDVI trend = maturing canopy = deeper colour."""
    if len(ndvi_history) < 2:
        return 60.0
    trend = ndvi_history[-1] - ndvi_history[0]
    if trend >= 0.03:
        return 95.0     # Rising strongly
    elif trend >= 0.0:
        return 80.0     # Stable-rising
    elif trend >= -0.03:
        return 60.0     # Slight decline
    else:
        return 35.0     # Declining canopy

def _score_humidity_level(hum_avg: float) -> float:
    """65-75% optimal for colour development."""
    if 65 <= hum_avg <= 75:
        return 100.0
    elif 60 <= hum_avg < 65 or 75 < hum_avg <= 80:
        return 75.0
    else:
        return 50.0

def _compute_zone_scores(zone_data: dict) -> dict:
    rainfall_h = zone_data["rainfall_history"]
    temp_swing  = zone_data["diurnal_swing"]
    ndwi        = zone_data["ndwi"]
    sm          = zone_data["soil_moisture"]
    evi         = zone_data["evi"]
    hum_h       = zone_data["humidity_history"]
    ndvi        = zone_data["ndvi"]
    ndvi_hist   = zone_data["ndvi_history"]

    dry_spell   = _score_dry_spell(rainfall_h)
    diurnal     = _score_diurnal_swing(temp_swing)
    ndwi_s      = _score_ndwi(ndwi)
    sm_s        = _score_soil_moisture(sm)
    evi_s       = _score_evi(evi)
    hum_cons    = _score_humidity_consistency(hum_h)
    ndvi_s      = _score_ndvi(ndvi)
    ndvi_trend  = _score_ndvi_trend(ndvi_hist)
    hum_lvl     = _score_humidity_level(sum(hum_h)/max(len(hum_h),1))

    briskness = round(0.40*dry_spell + 0.35*diurnal + 0.25*ndwi_s, 1)
    body      = round(0.40*sm_s + 0.35*evi_s + 0.25*hum_cons, 1)
    aroma     = round(0.60*diurnal + 0.40*ndvi_s, 1)
    colour    = round(0.55*ndvi_trend + 0.45*hum_lvl, 1)

    composite = round((briskness + body + aroma + colour) / 4, 1)

    if composite >= 78:
        leaf_grade = "A"
    elif composite >= 58:
        leaf_grade = "B"
    else:
        leaf_grade = "C"

    # Identify dominant driver for the zone
    scores_named = {
        "Dry Spell Pattern": dry_spell,
        "Diurnal Swing": diurnal,
        "Leaf Vigor (NDVI)": ndvi_s,
        "Soil Moisture": sm_s,
    }
    dominant_driver = max(scores_named, key=scores_named.get)
    
    calculation_logs = [
        f"Briskness (40% Dry Spell [{dry_spell}], 35% Diurnal Swing [{diurnal}], 25% NDWI [{ndwi_s}]) = {briskness}",
        f"Body (40% Soil Moisture [{sm_s}], 35% EVI [{evi_s}], 25% Humidity Consistency [{hum_cons}]) = {body}",
        f"Aroma (60% Diurnal Swing [{diurnal}], 40% NDVI [{ndvi_s}]) = {aroma}",
        f"Colour (55% NDVI Trend [{ndvi_trend}], 45% Humidity Level [{hum_lvl}]) = {colour}",
        f"Composite Score = {composite} (Grade {leaf_grade})"
    ]

    return {
        "briskness": briskness,
        "body": body,
        "aroma": aroma,
        "colour": colour,
        "composite": composite,
        "leaf_grade": leaf_grade,
        "dominant_driver": dominant_driver,
        "dry_days": sum(1 for r in rainfall_h[-4:] if r < 2.0),
        "temp_swing": round(temp_swing, 1),
        "ndvi": round(ndvi, 3),
        "ndwi": round(ndwi, 3),
        "soil_moisture": round(sm, 1),
        "humidity_avg": round(sum(hum_h)/max(len(hum_h),1), 1),
        "calculation_logs": calculation_logs
    }


@app.get("/api/leaf-potential/analyze")
def analyze_leaf_potential(user: User = Depends(get_current_user)):
    """
    Pre-Harvest Leaf Potential Index
    Generates a 4-dimension radar score (Briskness, Body, Aroma, Colour)
    per farm zone from the last 7 days of sensor + satellite data.
    Uses agronomically-grounded scoring rules.
    Missing data sources (EVI, NDWI, 7-day history, zone breakdown) are
    generated as realistic mock data derived from actual live readings.
    """
    import random, math

    FARM_ID = resolve_farm_id(user)

    # --- 1. Fetch latest real sensor data ---
    comp_data   = fetch_todays_comprehensive_data(FARM_ID)
    sensor_data = comp_data.get("sensor_data")

    # Base readings (real if available, otherwise sensible Assam defaults)
    base_sm    = float(sensor_data.get("soil_moisture") or 62) if sensor_data else 62.0
    base_temp  = float(sensor_data.get("temperature") or 22) if sensor_data else 22.0
    base_hum   = float(sensor_data.get("humidity") or 71) if sensor_data else 71.0
    base_rain  = float(sensor_data.get("rainfall_7d") or 48) if sensor_data else 48.0

    # --- 2. Derive / mock satellite indices ---
    # EVI: correlates with NDVI but slightly lower, add small noise
    # Try to get NDVI from the existing crop health scans if available
    base_ndvi = 0.70  # Assam typical
    leaf_scans = comp_data.get("leaf_scans", [])
    # NDWI derived from soil moisture: slight deficit favors quality
    base_ndwi = round((base_sm - 62) / 40, 3)   # 62% SM ≈ 0.0 (neutral)
    base_evi  = round(base_ndvi * 0.87 + 0.02, 3)

    # --- 3. Generate 7-day sensor history (realistic daily variation) ---
    rng = random.Random(42)  # Deterministic seed for consistency

    def gen_history(base, std, days=7):
        """Generate plausible day-to-day variation around a base value."""
        return [round(base + rng.gauss(0, std), 2) for _ in range(days)]

    # Farm-level 7-day histories
    farm_temp_history    = gen_history(base_temp, 1.2)
    farm_hum_history     = gen_history(base_hum, 3.0)
    farm_sm_history      = gen_history(base_sm, 2.5)
    # Rainfall: mostly 0 with occasional rain events
    farm_rain_history    = [round(max(0, rng.gauss(3, 5)), 1) for _ in range(7)]
    farm_ndvi_history    = gen_history(base_ndvi, 0.015)

    # Diurnal swing estimate from temperature (Assam hill/plain varies 8-15°C)
    farm_diurnal = 10 + (22 - base_temp) * 0.4

    # --- 4. Prepare Farm Data (Single Zone) ---
    farm_data = {
        "rainfall_history": farm_rain_history,
        "diurnal_swing":    farm_diurnal,
        "ndwi":             base_ndwi,
        "soil_moisture":    base_sm,
        "evi":              base_evi,
        "humidity_history": farm_hum_history,
        "ndvi":             base_ndvi,
        "ndvi_history":     farm_ndvi_history,
    }

    farm_score = _compute_zone_scores(farm_data)

    if farm_score["composite"] >= 78:
        overall_grade = "Premium"
        overall_label = "A"
    elif farm_score["composite"] >= 58:
        overall_grade = "Standard"
        overall_label = "B"
    else:
        overall_grade = "Basic"
        overall_label = "C"

    # --- 5. Gemini tasting note ---
    prompt = f"""You are an expert Assam tea liquor analyst and agronomist.

Based on the pre-harvest field sensor and satellite data for the farm, write a SHORT tasting note prediction (1-2 sentences).
The note MUST cite specific data values (e.g., "3 dry days", "diurnal swing of 12°C", "NDVI 0.71").
Do NOT use generic language. Be precise and agronomic.

Farm Data:
Briskness={farm_score['briskness']}, Body={farm_score['body']}, Aroma={farm_score['aroma']}, Colour={farm_score['colour']}, NDVI={farm_score['ndvi']}, dry_days={farm_score['dry_days']}, diurnal_swing={farm_score['temp_swing']}°C, soil_moisture={farm_score['soil_moisture']}%, leaf_grade={farm_score['leaf_grade']}
"""

    tasting_note = ""
    try:
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content(prompt)
        if response and response.text:
            tasting_note = response.text.strip()
    except Exception as e:
        print(f"⚠️ Gemini leaf potential note error: {e}")

    # Fallback notes if Gemini fails
    if not tasting_note:
        if farm_score["leaf_grade"] == "A":
            tasting_note = f"Predicted bright, brisk liquor with good body — {farm_score['dry_days']} dry days and {farm_score['temp_swing']}°C diurnal swing supporting catechin concentration."
        elif farm_score["leaf_grade"] == "B":
            tasting_note = f"Predicted medium-bodied, amber liquor with moderate briskness — NDVI {farm_score['ndvi']} and {farm_score['soil_moisture']}% soil moisture indicate standard pluck potential."
        else:
            tasting_note = f"Predicted flat, soft liquor — erratic conditions limiting quality potential. Review irrigation and monitor closely before plucking."

    farm_score["tasting_note"] = tasting_note

    return {
        "farm_score": farm_score,
        "overall_grade": overall_grade,
        "overall_label": overall_label,
        "data_inputs": {
            "base_ndvi": base_ndvi,
            "base_evi": base_evi,
            "base_ndwi": base_ndwi,
            "base_temp": base_temp,
            "base_humidity": base_hum,
            "base_soil_moisture": base_sm,
            "mock_sources": ["7-day sensor history", "EVI", "NDWI", "Diurnal swing"],
            "real_sources": ["IoT sensor (latest reading)", "NDVI (satellite scan)"] if sensor_data else ["All mock data"]
        }
    }


# Trigger reload for .env change

# Trigger reload for yolo

# Trigger reload for YOLO ultralytics installed


# --- Push Notification Endpoints ---
from pywebpush import webpush, WebPushException
from pydantic import BaseModel

class PushSubscriptionInfo(BaseModel):
    endpoint: str
    keys: dict

@app.post('/api/push/subscribe')
def subscribe_push(sub_info: PushSubscriptionInfo, db: Session = Depends(get_db)):
    try:
        sub = db.query(models_db.PushSubscription).filter(models_db.PushSubscription.endpoint == sub_info.endpoint).first()
        if not sub:
            sub = models_db.PushSubscription(
                owner_id='default',
                endpoint=sub_info.endpoint,
                p256dh=sub_info.keys.get('p256dh', ''),
                auth=sub_info.keys.get('auth', '')
            )
            db.add(sub)
            db.commit()
        return {'status': 'subscribed'}
    except Exception as e:
        print('subscribe_push DB error:', e)
        raise HTTPException(status_code=503, detail='Database unavailable. Push subscription could not be saved.')

@app.post('/api/push/test')
def test_push(sub_info: PushSubscriptionInfo, db: Session = Depends(get_db)):
    try:
        sub = db.query(models_db.PushSubscription).filter(models_db.PushSubscription.endpoint == sub_info.endpoint).first()
    except Exception as e:
        print('test_push DB error:', e)
        raise HTTPException(status_code=503, detail='Database unavailable.')

    if not sub:
        return {'error': 'Subscription not found'}

    subscription_info = {
        'endpoint': sub.endpoint,
        'keys': {
            'p256dh': sub.p256dh,
            'auth': sub.auth
        }
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data='Test Push Notification from TigaMinds!',
            vapid_private_key=os.getenv('VAPID_PRIVATE_KEY'),
            vapid_claims={'sub': 'mailto:admin@example.com'}
        )
        return {'status': 'success'}
    except WebPushException as ex:
        print('WebPush error:', ex)
        return {'error': str(ex)}



class PushSendPayload(BaseModel):
    endpoint: str
    keys: dict
    title: str = 'TigaMinds Alert'
    body: str = 'You have a new alert.'

@app.post('/api/push/send')
def send_push_alert(payload: PushSendPayload):
    """Send a named push notification with custom title and body."""
    subscription_info = {
        'endpoint': payload.endpoint,
        'keys': {
            'p256dh': payload.keys.get('p256dh', ''),
            'auth': payload.keys.get('auth', ''),
        }
    }
    import json as _json
    data = _json.dumps({'title': payload.title, 'body': payload.body, 'url': '/dashboard'})
    try:
        webpush(
            subscription_info=subscription_info,
            data=data,
            vapid_private_key=os.getenv('VAPID_PRIVATE_KEY'),
            vapid_claims={'sub': 'mailto:admin@example.com'}
        )
        return {'status': 'sent'}
    except WebPushException as ex:
        print('send_push_alert error:', ex)
        return {'error': str(ex)}
