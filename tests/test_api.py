import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)

def test_root_endpoint():
    """Test the root endpoint returns the welcome message"""
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome to the Job Finder API" in response.json()["message"]

def test_get_sources():
    """Test the sources endpoint returns the expected sources"""
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    
    assert "sources" in data
    sources = data["sources"]
    assert len(sources) == 3
    
    source_names = [source["name"] for source in sources]
    assert "LinkedIn" in source_names
    assert "Indeed" in source_names
    assert "Glassdoor" in source_names

def test_search_jobs_input_validation():
    """Test that the API validates input properly"""
    # Missing required fields
    response = client.post("/api/search", json={
        "position": "Developer"
        # Missing other required fields
    })
    assert response.status_code == 422
    
    # Invalid job nature
    response = client.post("/api/search", json={
        "position": "Full Stack Engineer",
        "experience": "2 years",
        "salary": "70,000 PKR to 120,000 PKR",
        "jobNature": "",  # Empty
        "location": "Peshawar, Pakistan",
        "skills": "full stack, MERN"
    })
    assert response.status_code == 422

# Mocking would be needed for proper search testing
@pytest.mark.asyncio
async def test_search_jobs_mock(monkeypatch):
    """
    Test the search endpoint with mocked scrapers
    
    This is a placeholder for a real test that would use mocking
    to avoid actual web scraping during tests.
    """
    # This would require mocking the scrapers and LLM processor
    pass
