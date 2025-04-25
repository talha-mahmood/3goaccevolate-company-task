from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uvicorn
import os
from dotenv import load_dotenv

from models.request import JobSearchRequest
from models.job import JobResponse
from scrapers.linkedin import LinkedInScraper
from scrapers.indeed import IndeedScraper
from scrapers.glassdoor import GlassdoorScraper
from utils.llm_processor import LLMProcessor

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Job Finder API",
    description="API that fetches relevant job listings from multiple sources",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize scrapers
linkedin_scraper = LinkedInScraper()
indeed_scraper = IndeedScraper()
glassdoor_scraper = GlassdoorScraper()

# Initialize LLM processor
llm_processor = LLMProcessor()

@app.get("/")
async def root():
    return {"message": "Welcome to the Job Finder API! Go to /docs for API documentation."}

@app.get("/api/sources")
async def get_sources():
    """Get available job sources"""
    return {
        "sources": [
            {"name": "LinkedIn", "status": "active"},
            {"name": "Indeed", "status": "active"},
            {"name": "Glassdoor", "status": "active"}
        ]
    }

@app.post("/api/search", response_model=JobResponse)
async def search_jobs(job_request: JobSearchRequest):
    """
    Search for jobs based on provided criteria
    """
    try:
        # Scrape jobs from different sources
        tasks = [
            linkedin_scraper.scrape(job_request),
            indeed_scraper.scrape(job_request),
            glassdoor_scraper.scrape(job_request)
        ]
        
        # Run scrapers in parallel
        job_results = await asyncio.gather(*tasks)
        
        # Flatten the list of jobs
        all_jobs = []
        for jobs in job_results:
            all_jobs.extend(jobs)
        
        # Filter jobs for relevance using LLM
        relevant_jobs = await llm_processor.filter_jobs_by_relevance(
            all_jobs, 
            job_request
        )
        
        return {"relevant_jobs": relevant_jobs}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching jobs: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
