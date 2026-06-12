import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

# Create an in-memory SQLite database for testing the API logic
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the database dependency in the FastAPI app
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_list_jobs_empty():
    response = client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 0

def test_upload_invalid_file_type():
    # Upload a txt file instead of csv
    files = {"file": ("test.txt", b"some data", "text/plain")}
    response = client.post("/jobs/upload", files=files)
    assert response.status_code == 400
    assert "Only CSV files accepted" in response.json()["detail"]

def test_upload_empty_csv():
    # Upload an empty csv
    files = {"file": ("test.csv", b"", "text/csv")}
    response = client.post("/jobs/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_upload_invalid_csv_headers():
    # Upload csv with wrong headers
    files = {"file": ("test.csv", b"name,age,city\nJohn,30,New York", "text/csv")}
    response = client.post("/jobs/upload", files=files)
    assert response.status_code == 400
    assert "Invalid CSV structure" in response.json()["detail"]
