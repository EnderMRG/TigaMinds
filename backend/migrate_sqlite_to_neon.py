import sqlite3
import os
from dotenv import load_dotenv
load_dotenv()
from database import engine, Base, SessionLocal
from models_db import WeatherCache, ElevationCache, RouteCorridor, CropHealthScan, Scheme

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chainet_cache.db')

def migrate_data():
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"SQLite DB not found at {SQLITE_DB_PATH}. Exiting.")
        return

    print("Connecting to NeonDB and creating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    
    print("Connecting to SQLite database...")
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    db = SessionLocal()
    
    try:
        # Migrate WeatherCache
        print("Migrating WeatherCache...")
        c.execute("SELECT * FROM weather_cache")
        weather_rows = c.fetchall()
        for row in weather_rows:
            existing = db.query(WeatherCache).filter(
                WeatherCache.lat == row['lat'],
                WeatherCache.lon == row['lon'],
                WeatherCache.date == row['date']
            ).first()
            if not existing:
                db.add(WeatherCache(
                    lat=row['lat'],
                    lon=row['lon'],
                    date=row['date'],
                    precipitation_mm=row['precipitation_mm'],
                    precipitation_probability=row['precipitation_probability'],
                    cached_at=row['cached_at']
                ))
        db.commit()

        # Migrate ElevationCache
        print("Migrating ElevationCache...")
        c.execute("SELECT * FROM elevation_cache")
        elevation_rows = c.fetchall()
        for row in elevation_rows:
            existing = db.query(ElevationCache).filter(
                ElevationCache.lat == row['lat'],
                ElevationCache.lon == row['lon']
            ).first()
            if not existing:
                db.add(ElevationCache(
                    lat=row['lat'],
                    lon=row['lon'],
                    elevation_m=row['elevation_m'],
                    cached_at=row['cached_at']
                ))
        db.commit()

        # Migrate RouteCorridor
        print("Migrating RouteCorridor...")
        c.execute("SELECT * FROM route_corridors")
        corridor_rows = c.fetchall()
        for row in corridor_rows:
            existing = db.query(RouteCorridor).filter(
                RouteCorridor.name == row['name']
            ).first()
            if not existing:
                db.add(RouteCorridor(
                    name=row['name'],
                    min_lat=row['min_lat'],
                    max_lat=row['max_lat'],
                    min_lon=row['min_lon'],
                    max_lon=row['max_lon'],
                    historical_delay_flag=row['historical_delay_flag'],
                    hazard_type=row['hazard_type'] if 'hazard_type' in row.keys() else None,
                    hazard_description=row['hazard_description'] if 'hazard_description' in row.keys() else None,
                    severity=row['severity'] if 'severity' in row.keys() else None
                ))
        db.commit()

        # Migrate CropHealthScan
        print("Migrating CropHealthScan...")
        c.execute("SELECT * FROM crop_health_scans")
        scan_rows = c.fetchall()
        for row in scan_rows:
            db.add(CropHealthScan(
                field_id=row['field_id'],
                polygon_geojson=row['polygon_geojson'],
                ndvi=row['ndvi'],
                evi=row['evi'],
                ndwi=row['ndwi'],
                classification=row['classification'],
                scene_date=row['scene_date'],
                created_at=row['created_at']
            ))
        db.commit()

        # Migrate Scheme
        print("Migrating Scheme...")
        c.execute("SELECT * FROM schemes")
        scheme_rows = c.fetchall()
        for row in scheme_rows:
            existing = db.query(Scheme).filter(
                Scheme.name == row['name']
            ).first()
            if not existing:
                db.add(Scheme(
                    name=row['name'],
                    provider=row['provider'],
                    category=row['category'],
                    subsidy_details=row['subsidy_details'],
                    eligibility_criteria=row['eligibility_criteria'],
                    application_window=row['application_window'],
                    source_url=row['source_url'],
                    region_specificity=row['region_specificity'] if 'region_specificity' in row.keys() else 'National'
                ))
        db.commit()

        print("Migration from SQLite to NeonDB completed successfully!")
    
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
    finally:
        db.close()
        conn.close()

if __name__ == "__main__":
    migrate_data()
