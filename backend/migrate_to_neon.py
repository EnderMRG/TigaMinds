import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from database import engine, Base, SessionLocal, metadata
from models_db import Farm, Sensor, SensorReading, LeafScan, ActionPlan
from sqlalchemy import text
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Firebase
firebase_creds = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN")
}

try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(firebase_creds)
    firebase_admin.initialize_app(cred)

db_firestore = firestore.client()

def dt_from_fb(ts):
    if not ts:
        return datetime.utcnow()
    # Handle Firestore DatetimeWithNanoseconds
    if hasattr(ts, 'timestamp'):
        return datetime.fromtimestamp(ts.timestamp())
    if isinstance(ts, datetime):
        return ts
    return datetime.utcnow()

def migrate_data():
    print("Starting Migration to Neon DB (PostgreSQL)...")
    
    # 1. Create Schema if not exists
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS tigaminds;"))
        conn.commit()
    
    # 2. Create tables
    Base.metadata.create_all(bind=engine)
    print("Schema and Tables created.")
    
    db = SessionLocal()
    
    try:
        # Migrate Farms
        print("Migrating Farms...")
        farms_ref = db_firestore.collection("farms").stream()
        for farm_doc in farms_ref:
            farm_data = farm_doc.to_dict()
            farm_id = farm_doc.id
            
            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            if not farm:
                farm = Farm(
                    id=farm_id,
                    name=farm_data.pop("name", f"Farm {farm_id}"),
                    owner_id=farm_data.pop("owner_id", None),
                    location=farm_data.pop("location", None),
                    extra_data=farm_data
                )
                db.add(farm)
                db.commit()
            
            # Migrate Sensors for this farm
            sensors_ref = db_firestore.collection("farms").document(farm_id).collection("sensors").stream()
            for sensor_doc in sensors_ref:
                sensor_data = sensor_doc.to_dict()
                sensor_id = sensor_doc.id
                
                sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
                if not sensor:
                    sensor = Sensor(
                        id=sensor_id,
                        farm_id=farm_id,
                        type=sensor_data.pop("type", "environment"),
                        name=sensor_data.pop("name", f"Sensor {sensor_id}"),
                        status=sensor_data.pop("status", "active"),
                        extra_data=sensor_data
                    )
                    db.add(sensor)
                    db.commit()
                
                # Migrate Readings for this sensor
                readings_ref = db_firestore.collection("farms").document(farm_id).collection("sensors").document(sensor_id).collection("readings").stream()
                readings_to_add = []
                for read_doc in readings_ref:
                    read_data = read_doc.to_dict()
                    ts = dt_from_fb(read_data.pop("timestamp", None))
                    
                    reading = SensorReading(
                        sensor_id=sensor_id,
                        timestamp=ts,
                        soil_moisture=read_data.pop("soil_moisture", None),
                        temperature=read_data.pop("temperature", None),
                        humidity=read_data.pop("humidity", None),
                        rainfall_7d=read_data.pop("rainfall_7d", None),
                        extra_data=read_data
                    )
                    readings_to_add.append(reading)
                
                if readings_to_add:
                    db.add_all(readings_to_add)
                    db.commit()
                    print("  - Migrated {len(readings_to_add)} readings for sensor {sensor_id}")
            
            # Migrate Leaf Scans
            scans_ref = db_firestore.collection("farms").document(farm_id).collection("leaf_scans").stream()
            for scan_doc in scans_ref:
                scan_data = scan_doc.to_dict()
                scan_id = scan_doc.id
                
                scan = db.query(LeafScan).filter(LeafScan.id == scan_id).first()
                if not scan:
                    ts = dt_from_fb(scan_data.pop("timestamp", None))
                    scan = LeafScan(
                        id=scan_id,
                        farm_id=farm_id,
                        timestamp=ts,
                        image_url=scan_data.pop("image_url", None),
                        result=scan_data.pop("result", None),
                        confidence=scan_data.pop("confidence", None),
                        disease_name=scan_data.pop("disease_name", None),
                        recommendation=scan_data.pop("recommendation", None),
                        extra_data=scan_data
                    )
                    db.add(scan)
                    db.commit()
            
            # Migrate Action Plans
            plans_ref = db_firestore.collection("farms").document(farm_id).collection("action_plans").stream()
            for plan_doc in plans_ref:
                plan_data = plan_doc.to_dict()
                plan_id = plan_doc.id
                
                plan = db.query(ActionPlan).filter(ActionPlan.id == plan_id).first()
                if not plan:
                    ts = dt_from_fb(plan_data.pop("timestamp", None))
                    plan = ActionPlan(
                        id=plan_id,
                        farm_id=farm_id,
                        timestamp=ts,
                        title=plan_data.pop("title", None),
                        description=plan_data.pop("description", None),
                        status=plan_data.pop("status", None),
                        tasks=plan_data.pop("tasks", None),
                        extra_data=plan_data
                    )
                    db.add(plan)
                    db.commit()
                    
        print("Data Migration Completed Successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate_data()
