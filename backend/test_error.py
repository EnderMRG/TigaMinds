import traceback
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
try:
    response = client.get('/api/crop-health/history/demo_field', headers={'Authorization': 'Bearer demo_token'})
    print(response.status_code)
    try:
        print(response.json())
    except:
        print(response.text)
except Exception as e:
    traceback.print_exc()
