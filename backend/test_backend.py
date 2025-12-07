from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Roadmap Tracer API"}

def test_create_roadmap():
    # Clean up db if needed (it uses a file, so maybe just use a unique name)
    name = "Test Roadmap"
    text = "Month 1\nWeek 1\n- Task 1"
    
    # Try delete first to ensure clean state
    # We need to find it first? No, just create and ignore error if exists for this simple test
    # Or better, use a unique name
    import time
    name = f"Test Roadmap {time.time()}"
    
    response = client.post("/roadmaps", json={"name": name, "text": text})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    return data['id']

def test_get_roadmaps():
    response = client.get("/roadmaps")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

if __name__ == "__main__":
    try:
        test_read_main()
        rid = test_create_roadmap()
        test_get_roadmaps()
        print("Backend tests passed!")
    except Exception as e:
        print(f"Backend tests failed: {e}")
