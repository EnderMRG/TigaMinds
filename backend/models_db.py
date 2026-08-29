from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Farm(Base):
    __tablename__ = "farms"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    owner_id = Column(String, nullable=True)
    location = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    sensors = relationship("Sensor", back_populates="farm")
    leaf_scans = relationship("LeafScan", back_populates="farm")
    action_plans = relationship("ActionPlan", back_populates="farm")

class Sensor(Base):
    __tablename__ = "sensors"
    
    id = Column(String, primary_key=True, index=True)
    farm_id = Column(String, ForeignKey("farms.id"), index=True)
    type = Column(String, nullable=True)
    name = Column(String, nullable=True)
    status = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    farm = relationship("Farm", back_populates="sensors")
    readings = relationship("SensorReading", back_populates="sensor")

class SensorReading(Base):
    __tablename__ = "readings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(String, ForeignKey("sensors.id"), index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    soil_moisture = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    rainfall_7d = Column(Float, nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    sensor = relationship("Sensor", back_populates="readings")

class LeafScan(Base):
    __tablename__ = "leaf_scans"
    
    id = Column(String, primary_key=True, index=True)
    farm_id = Column(String, ForeignKey("farms.id"), index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    image_url = Column(String, nullable=True)
    result = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    disease_name = Column(String, nullable=True)
    recommendation = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    farm = relationship("Farm", back_populates="leaf_scans")

class ActionPlan(Base):
    __tablename__ = "action_plans"
    
    id = Column(String, primary_key=True, index=True)
    farm_id = Column(String, ForeignKey("farms.id"), index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    title = Column(String, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String, nullable=True)
    tasks = Column(JSON, nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    farm = relationship("Farm", back_populates="action_plans")

class WeatherCache(Base):
    __tablename__ = "weather_cache"
    
    # Composite primary key (lat, lon, date) isn't straightforward without multi-column PK
    # Alternatively, create a surrogate key or use composite.
    # Using composite PK:
    lat = Column(Float, primary_key=True)
    lon = Column(Float, primary_key=True)
    date = Column(String, primary_key=True)
    precipitation_mm = Column(Float, nullable=True)
    precipitation_probability = Column(Float, nullable=True)
    cached_at = Column(String, nullable=True)

class ElevationCache(Base):
    __tablename__ = "elevation_cache"
    
    lat = Column(Float, primary_key=True)
    lon = Column(Float, primary_key=True)
    elevation_m = Column(Float, nullable=True)
    cached_at = Column(String, nullable=True)

class RouteCorridor(Base):
    __tablename__ = "route_corridors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=True)
    min_lat = Column(Float, nullable=True)
    max_lat = Column(Float, nullable=True)
    min_lon = Column(Float, nullable=True)
    max_lon = Column(Float, nullable=True)
    historical_delay_flag = Column(Float, nullable=True)
    hazard_type = Column(String, nullable=True)
    hazard_description = Column(String, nullable=True)
    severity = Column(String, nullable=True)

class CropHealthScan(Base):
    __tablename__ = "crop_health_scans"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(String, index=True, nullable=True)
    polygon_geojson = Column(String, nullable=True) # Storing as text since it's JSON dump
    ndvi = Column(Float, nullable=True)
    evi = Column(Float, nullable=True)
    ndwi = Column(Float, nullable=True)
    classification = Column(String, nullable=True)
    scene_date = Column(String, nullable=True)
    created_at = Column(String, nullable=True)

class Scheme(Base):
    __tablename__ = "schemes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=True)
    provider = Column(String, nullable=True)
    category = Column(String, nullable=True)
    subsidy_details = Column(String, nullable=True)
    eligibility_criteria = Column(String, nullable=True)
    application_window = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    region_specificity = Column(String, default='National')

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String, index=True, nullable=True)
    endpoint = Column(String, unique=True, nullable=False)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

