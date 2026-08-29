from database import SessionLocal
from models_db import Farm, Sensor, SensorReading, LeafScan, ActionPlan
import datetime
import uuid

# Mock SERVER_TIMESTAMP
SERVER_TIMESTAMP = "SERVER_TIMESTAMP"

class Query:
    DESCENDING = "DESCENDING"
    ASCENDING = "ASCENDING"

class MockDocumentSnapshot:
    def __init__(self, id, data):
        self.id = id
        self._data = data
        
    def to_dict(self):
        return {k: v for k, v in self._data.items() if v is not None}

class MockQuery:
    def __init__(self, collection):
        self.collection = collection
        self._order_by = None
        self._direction = None
        self._limit = None
        self._where = []
        
    def where(self, field, op, value):
        self._where.append((field, op, value))
        return self
        
    def order_by(self, field, direction=Query.ASCENDING):
        self._order_by = field
        self._direction = direction
        return self
        
    def limit(self, count):
        self._limit = count
        return self
        
    def stream(self):
        db = SessionLocal()
        try:
            path = self.collection.path
            
            if len(path) == 3 and path[0] == "farms" and path[2] == "leaf_scans":
                farm_id = path[1]
                q = db.query(LeafScan).filter(LeafScan.farm_id == farm_id)
                if self._order_by == "timestamp":
                    if self._direction == Query.DESCENDING:
                        q = q.order_by(LeafScan.timestamp.desc())
                    else:
                        q = q.order_by(LeafScan.timestamp.asc())
                if self._limit:
                    q = q.limit(self._limit)
                
                if self._where:
                    for field, op, value in self._where:
                        if field == "timestamp":
                            if op == ">=":
                                q = q.filter(LeafScan.timestamp >= value)
                            elif op == "<=":
                                q = q.filter(LeafScan.timestamp <= value)
                            elif op == "==":
                                q = q.filter(LeafScan.timestamp == value)
                            elif op == ">":
                                q = q.filter(LeafScan.timestamp > value)
                            elif op == "<":
                                q = q.filter(LeafScan.timestamp < value)
                
                results = q.all()
                return iter([MockDocumentSnapshot(r.id, {
                    "timestamp": r.timestamp,
                    "image_url": r.image_url,
                    "result": r.result,
                    "confidence": r.confidence,
                    "disease_name": r.disease_name,
                    "recommendation": r.recommendation,
                    **(r.extra_data or {})
                }) for r in results])

            elif len(path) == 3 and path[0] == "farms" and path[2] == "action_plans":
                farm_id = path[1]
                q = db.query(ActionPlan).filter(ActionPlan.farm_id == farm_id)
                if self._order_by == "timestamp":
                    if self._direction == Query.DESCENDING:
                        q = q.order_by(ActionPlan.timestamp.desc())
                    else:
                        q = q.order_by(ActionPlan.timestamp.asc())
                if self._limit:
                    q = q.limit(self._limit)
                
                if self._where:
                    for field, op, value in self._where:
                        if field == "timestamp":
                            if op == ">=":
                                q = q.filter(ActionPlan.timestamp >= value)
                            elif op == "<=":
                                q = q.filter(ActionPlan.timestamp <= value)
                            elif op == "==":
                                q = q.filter(ActionPlan.timestamp == value)
                            elif op == ">":
                                q = q.filter(ActionPlan.timestamp > value)
                            elif op == "<":
                                q = q.filter(ActionPlan.timestamp < value)
                
                results = q.all()
                return iter([MockDocumentSnapshot(r.id, {
                    "timestamp": r.timestamp,
                    "title": r.title,
                    "description": r.description,
                    "status": r.status,
                    "tasks": r.tasks,
                    **(r.extra_data or {})
                }) for r in results])
                
            elif len(path) == 5 and path[0] == "farms" and path[2] == "sensors" and path[4] == "readings":
                farm_id = path[1]
                sensor_id = path[3]
                q = db.query(SensorReading).filter(SensorReading.sensor_id == sensor_id)
                if self._order_by == "timestamp":
                    if self._direction == Query.DESCENDING:
                        q = q.order_by(SensorReading.timestamp.desc())
                    else:
                        q = q.order_by(SensorReading.timestamp.asc())
                if self._limit:
                    q = q.limit(self._limit)
                
                if self._where:
                    for field, op, value in self._where:
                        if field == "timestamp":
                            if op == ">=":
                                q = q.filter(SensorReading.timestamp >= value)
                            elif op == "<=":
                                q = q.filter(SensorReading.timestamp <= value)
                            elif op == "==":
                                q = q.filter(SensorReading.timestamp == value)
                            elif op == ">":
                                q = q.filter(SensorReading.timestamp > value)
                            elif op == "<":
                                q = q.filter(SensorReading.timestamp < value)
                
                results = q.all()
                return iter([MockDocumentSnapshot(str(r.id), {
                    "timestamp": r.timestamp,
                    "soil_moisture": r.soil_moisture if r.soil_moisture is not None else 0,
                    "temperature": r.temperature if r.temperature is not None else 0,
                    "humidity": r.humidity if r.humidity is not None else 0,
                    "rainfall_7d": r.rainfall_7d if r.rainfall_7d is not None else 0,
                    **(r.extra_data or {})
                }) for r in results])
                
            else:
                print(f"⚠️ MockQuery unsupported stream for path {path}")
                return iter([])
        finally:
            db.close()

class MockCollection:
    def __init__(self, path):
        self.path = path

    def document(self, id):
        return MockDocument(self.path + [id])

    def where(self, field, op, value):
        return MockQuery(self).where(field, op, value)

    def order_by(self, field, direction=Query.ASCENDING):
        return MockQuery(self).order_by(field, direction)

    def limit(self, count):
        return MockQuery(self).limit(count)

    def stream(self):
        return MockQuery(self).stream()
        
    def add(self, data):
        db = SessionLocal()
        try:
            doc_id = str(uuid.uuid4())
            # Replace SERVER_TIMESTAMP with actual time
            for k, v in data.items():
                if v == SERVER_TIMESTAMP:
                    data[k] = datetime.datetime.utcnow()
                    
            if len(self.path) == 3 and self.path[0] == "farms" and self.path[2] == "leaf_scans":
                farm_id = self.path[1]
                scan = LeafScan(
                    id=doc_id,
                    farm_id=farm_id,
                    timestamp=data.pop("timestamp", datetime.datetime.utcnow()),
                    image_url=data.pop("image_url", None),
                    result=data.pop("result", None),
                    confidence=data.pop("confidence", None),
                    disease_name=data.pop("disease_name", None),
                    recommendation=data.pop("recommendation", None),
                    extra_data=data
                )
                db.add(scan)
                db.commit()
            elif len(self.path) == 3 and self.path[0] == "farms" and self.path[2] == "action_plans":
                farm_id = self.path[1]
                plan = ActionPlan(
                    id=doc_id,
                    farm_id=farm_id,
                    timestamp=data.pop("timestamp", datetime.datetime.utcnow()),
                    title=data.pop("title", None),
                    description=data.pop("description", None),
                    status=data.pop("status", None),
                    tasks=data.pop("tasks", None),
                    extra_data=data
                )
                db.add(plan)
                db.commit()
            else:
                print(f"⚠️ MockCollection unsupported add for path {self.path}")
                
            return None, MockDocument(self.path + [doc_id])  # add returns (update_time, document_ref)
        finally:
            db.close()

class MockDocument:
    def __init__(self, path):
        self.path = path

    def collection(self, name):
        return MockCollection(self.path + [name])

class MockFirestoreClient:
    def collection(self, name):
        return MockCollection([name])

def client():
    return MockFirestoreClient()
