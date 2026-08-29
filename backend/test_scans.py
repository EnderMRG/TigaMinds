from database import SessionLocal
from main import CropHealthScan
import json

db = SessionLocal()
scans = db.query(CropHealthScan).order_by(CropHealthScan.scene_date.desc()).limit(15).all()
for s in scans:
    print(f"ID: {s.field_id}, Date: {s.scene_date}, NDVI: {s.ndvi}, EVI: {s.evi}")
