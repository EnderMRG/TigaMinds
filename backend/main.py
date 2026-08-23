# MUST BE FIRST - numpy compatibility layer before ANY imports that use numpy
import sys
import pathlib
import platform

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

db = firestore.client()

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
security = HTTPBearer()

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
        if not credentials:
            raise HTTPException(status_code=401, detail="No credentials provided")

        token = credentials.credentials

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

# CORS - Support both local development and production
frontend_url = os.getenv("FRONTEND_URL", "")
allowed_origins = [
    "http://localhost:3000",  # Local development
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
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.onrender\.com",
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
    yolo_model = torch.hub.load('ultralytics/yolov5', 'custom', path='models/best.pt', force_reload=False, trust_repo=True)
    yolo_model.conf = 0.25  # Confidence threshold
    yolo_model.iou = 0.45   # NMS IOU threshold
    print("✅ YOLOv5 disease detection model loaded successfully")
except Exception as e:
    print(f"⚠️ YOLOv5 model loading failed: {e}")
    import traceback
    traceback.print_exc()
    yolo_model = None

index_to_label = {v: k for k, v in class_labels.items()}

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
    if cnn_grade.lower() == "healthy":
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
        "yolo_detections": yolo_detections  # Object detection results
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

@app.get("/api/farm/averages")
def get_farm_averages(user: User = Depends(get_current_user)):
    FARM_ID = resolve_farm_id(user)

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

    if not readings:
        return {"error": "No sensor data found"}

    df = pd.DataFrame(readings)

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

@app.get("/api/farm/soil-moisture-series")
def soil_moisture_series(user: User = Depends(get_current_user)):
    FARM_ID = resolve_farm_id(user)

    docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("sensors")
        .document("sensors_root")
        .collection("readings")
        .order_by("timestamp", direction=Query.DESCENDING)
        .limit(24)
        .stream()
    )

    series = []

    for doc in docs:
        d = doc.to_dict()
        if not d.get("timestamp"):
            continue

        series.append({
            "time": d["timestamp"].strftime("%d %b %H:%M"),
            "value": round(d["soil_moisture"], 1),
            "ts": d["timestamp"]
        })

    # ✅ THIS IS THE IMPORTANT LINE
    series.sort(key=lambda x: x["ts"])

    return [
        { "time": row["time"], "value": row["value"] }
        for row in series
    ]

@app.get("/api/farm/temperature-series")
def temperature_series(user: User = Depends(get_current_user)):
    FARM_ID = resolve_farm_id(user)

    docs = (
        db.collection("farms")
        .document(FARM_ID)
        .collection("sensors")
        .document("sensors_root")
        .collection("readings")
        .order_by("timestamp", direction=Query.DESCENDING)
        .limit(24)
        .stream()
    )

    series = []

    for doc in docs:
        d = doc.to_dict()
        if not d.get("timestamp"):
            continue

        series.append({
            "time": d["timestamp"].strftime("%d %b %H:%M"),
            "value": round(d["temperature"], 1),
            "ts": d["timestamp"]
        })

    series.sort(key=lambda x: x["ts"])

    return [
        {"time": row["time"], "value": row["value"]}
        for row in series
    ]


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

    latest = next(docs, None)
    if not latest:
        return {"error": "No IoT data available"}

    d = latest.to_dict()

    data = {
        "soil_moisture": d["soil_moisture"],
        "temperature": d["temperature"],
        "humidity": d["humidity"],
        "rainfall_7d": d["rainfall_7d"],
        "soil_ph": d.get("soil_ph", 5.2),
    }

    return run_cultivation_engine(data)


@app.get("/api/cultivation/smart-alert")
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

@app.post("/api/calculate-yield-strategy")
def calculate_yield_strategy(data: YieldInput):
    """
    Calculate 3 selling strategies based on yield input and real Guwahati market data
    """
    yield_kg = data.yield_kg
    
    if yield_kg <= 0:
        return {"error": "Yield must be greater than 0"}
    
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
    
    # Generate 3 selling strategies with REAL calculations
    strategies = [
        {
            "title": "Immediate Sale at Current Market Rate",
            "description": f"Sell {yield_kg} kg immediately at current Guwahati market rate of ₹{current_price}/kg. This approach minimizes storage costs and provides immediate cash flow. Best for farmers needing quick liquidity.",
            "expected_revenue": round(yield_kg * current_price, 2),
            "revenue_display": f"₹{int(yield_kg * current_price):,}",
            "timing": "Immediate (1-2 days)",
            "priority": "medium" if signal != "risk" else "high",
            "price_per_kg": current_price,
            "yield_impact": 0,
            "profit_change": 0
        },
        {
            "title": "Wait for Peak Demand Window",
            "description": f"Store yield and sell during {selling_window} when Guwahati prices are forecasted to reach ₹{forecast_price:.2f}/kg. Implement proper storage to maintain quality. Expected price increase of {forecast_increase_pct:+.1f}%.",
            "expected_revenue": round(yield_kg * forecast_price, 2),
            "revenue_display": f"₹{int(yield_kg * forecast_price):,} ({forecast_increase_pct:+.1f}%)",
            "timing": selling_window,
            "priority": "high" if signal == "opportunity" else "medium",
            "price_per_kg": forecast_price,
            "yield_impact": 0,
            "profit_change": round(yield_kg * (forecast_price - current_price), 2)
        },
        {
            "title": "Quality Improvement + Premium Sale",
            "description": f"Invest in post-harvest processing to improve grade quality. Target premium Guwahati buyers willing to pay 15-20% more (₹{current_price * 1.18:.2f}/kg) for superior quality tea. Requires additional processing time and investment of ~₹{int(yield_kg * 5):,}.",
            "expected_revenue": round(yield_kg * current_price * 1.18, 2),
            "revenue_display": f"₹{int(yield_kg * current_price * 1.18):,} (+18%)",
            "timing": "7-14 days (processing time)",
            "priority": "high" if signal != "risk" else "low",
            "price_per_kg": round(current_price * 1.18, 2),
            "yield_impact": -2,  # Small loss due to processing
            "profit_change": round(yield_kg * current_price * 0.18 - yield_kg * 5, 2)  # Premium minus processing cost
        }
    ]
    
    # Calculate projected outcomes based on selected approach
    selected = strategies[data.selected_approach]
    
    # Calculate comparative metrics
    base_revenue = yield_kg * current_price
    selected_revenue = selected["expected_revenue"]
    revenue_diff_pct = ((selected_revenue - base_revenue) / base_revenue) * 100
    
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
        
        # ===== RISK FACTORS (Section number depends on yield input) =====
        if sim_data.get('riskFactors'):
            # Section 6 if no yield, Section 8 if yield entered
            section_num = "8" if (data.yield_input and data.yield_input > 0) else "6"
            elements.append(Paragraph(f"{section_num}. Risk Factors Analysis", heading_style))
            
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
    sm = sensor_data.get("soil_moisture", 60)
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
    temp = sensor_data.get("temperature", 22)
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
    hum = sensor_data.get("humidity", 70)
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
    rain = sensor_data.get("rainfall_7d", 60)
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
        grade = scan.get("grade", "").lower()
        confidence = scan.get("confidence", 0.5)
        severity = scan.get("severity", "Low")
        
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
    
    signal = market_data.get("signal", "neutral")
    demand_index = market_data.get("demand_index", 50)
    volatility = market_data.get("volatility", 2)
    price_change_pct = market_data.get("price_change_pct", 0)
    
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
    diseased_scans = [s for s in leaf_scans if s.get("grade", "").lower() == "diseased"]
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
        diseased_scans = [s for s in leaf_scans if s.get("grade", "").lower() == "diseased"]
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