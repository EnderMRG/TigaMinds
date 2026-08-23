import os
import random
from datetime import datetime, timedelta, timezone
from google.cloud import firestore

def seed_demo_data():
    print("Seeding new mock data for demo_farm...")
    
    # Import initialized db from main.py
    from main import db
    
    # Target collection
    readings_ref = (
        db.collection("farms")
        .document("demo_farm")
        .collection("sensors")
        .document("sensors_root")
        .collection("readings")
    )
    
    # Delete old readings to keep it clean
    old_docs = readings_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
    batch = db.batch()
    count = 0
    for doc in old_docs:
        batch.delete(doc.reference)
        count += 1
    if count > 0:
        batch.commit()
        print(f"Deleted {count} old readings.")

    # Generate 24 hours of new mock data ending right now
    now = datetime.now(timezone.utc)
    new_batch = db.batch()
    
    for i in range(24):
        dt = now - timedelta(hours=(23 - i))
        
        # Base values with some realistic variance
        temp = random.uniform(18.0, 32.0)
        # Temp is higher in the middle of the day (roughly)
        hour = dt.hour
        if 10 <= hour <= 16:
            temp = random.uniform(25.0, 32.0)
        elif hour < 6 or hour > 20:
            temp = random.uniform(18.0, 22.0)
            
        doc_ref = readings_ref.document()
        new_batch.set(doc_ref, {
            "timestamp": dt,
            "soil_moisture": random.uniform(45.0, 65.0),
            "temperature": temp,
            "humidity": random.uniform(70.0, 85.0),
            "rainfall_7d": random.uniform(20.0, 60.0)
        })
        
    new_batch.commit()
    print("Successfully seeded 24 hours of fresh mock data!")

if __name__ == "__main__":
    seed_demo_data()
