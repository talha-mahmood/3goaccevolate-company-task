from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uvicorn
import os
import logging
from dotenv import load_dotenv
import time
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from models.request import JobSearchRequest
from models.job import JobResponse, Job
from scrapers.scraper_factory import ScraperFactory
from scrapers.mock_scraper import MockScraper
from utils.llm_processor import LLMProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Application state
app_state = {
    "health": "OK",
    "job_cache": {},
    "scrapers": {},
    "llm_processor": None
}

# Cache expiry time
cache_expiry = 3600  # Cache expiry in seconds (1 hour)

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize resources
    logging.info("Starting application and initializing resources...")
    try:
        # Initialize scrapers
        app_state["scrapers"] = ScraperFactory.create_scrapers()
        
        # Initialize LLM processor
        app_state["llm_processor"] = LLMProcessor()
        
        logging.info("Application startup complete")
    except Exception as e:
        logging.error(f"Error during startup: {str(e)}")
        app_state["health"] = f"ERROR: {str(e)}"
    
    yield
    
    # Shutdown: Clean up resources
    logging.info("Shutting down application...")
    # Clean up any connections or resources
    app_state["scrapers"] = {}
    app_state["llm_processor"] = None
    app_state["job_cache"] = {}
    logging.info("Application shutdown complete")

# Initialize FastAPI
app = FastAPI(
    title="Job Finder API",
    description="API that fetches relevant job listings from multiple sources",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint - returns API welcome message"""
    return {"message": "Welcome to the Job Finder API! Go to /docs for API documentation."}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": app_state["health"],
        "time": time.time(),
        "cache_entries": len(app_state["job_cache"]),
        "scrapers": list(app_state["scrapers"].keys())
    }

@app.get("/api/sources")
async def get_sources():
    """Get available job sources"""
    return {
        "sources": [
            {"name": source_name, "status": "active"} 
            for source_name in app_state["scrapers"].keys()
        ]
    }

@app.post("/api/search", response_model=JobResponse)
async def search_jobs(job_request: JobSearchRequest, background_tasks: BackgroundTasks):
    """
    Search for jobs based on provided criteria
    """
    try:
        logging.info(f"Searching for jobs: {job_request.position} in {job_request.location}")
        
        # Create a cache key
        cache_key = f"{job_request.position}_{job_request.location}_{job_request.jobNature}_{job_request.experience}"
        
        # Check cache
        if cache_key in app_state["job_cache"] and (time.time() - app_state["job_cache"][cache_key]["timestamp"] < cache_expiry):
            logging.info(f"Returning cached results for {cache_key}")
            return {"relevant_jobs": app_state["job_cache"][cache_key]["jobs"]}
        
        # Set a strict overall timeout for the entire operation
        overall_timeout = 30  # 30 seconds maximum for the entire operation
        
        # Create a task that will execute all the scraping
        scraping_task = asyncio.create_task(_execute_job_search(job_request))
        
        try:
            # Wait for the scraping task with a timeout
            all_jobs = await asyncio.wait_for(scraping_task, timeout=overall_timeout)
        except asyncio.TimeoutError:
            logging.error(f"Overall job search operation timed out after {overall_timeout} seconds")
            # Start the search in the background to cache results for next time
            background_tasks.add_task(refresh_job_data, job_request, cache_key)
            # Return empty results to avoid UI hanging
            return {"relevant_jobs": []}
        except Exception as e:
            logging.error(f"Error in job search operation: {str(e)}")
            # Return empty results on error
            return {"relevant_jobs": []}
        
        logging.info(f"Found {len(all_jobs)} jobs from all sources")
        
        # If no jobs were found, return empty results
        if not all_jobs:
            logging.warning("No jobs found from any source, returning empty results")
            # Schedule background task to try again
            background_tasks.add_task(refresh_job_data, job_request, cache_key)
            # Return empty results immediately
            return {"relevant_jobs": []}
        
        # Process with LLM with a shorter timeout
        relevant_jobs = await _process_with_llm(all_jobs, job_request)
        
        # Cache the results
        app_state["job_cache"][cache_key] = {
            "timestamp": time.time(),
            "jobs": relevant_jobs
        }
        
        return {"relevant_jobs": relevant_jobs}
    
    except Exception as e:
        logging.error(f"Error searching jobs: {str(e)}")
        # Return empty results on error
        return {"relevant_jobs": []}

# Add this new helper function for executing job search
async def _execute_job_search(job_request: JobSearchRequest) -> List[Job]:
    """Execute job search across all sources with proper timeout handling"""
    # Scrape jobs from different sources
    tasks = []
    
    for name, scraper in app_state["scrapers"].items():
        # Use timeouts from environment if available, otherwise use defaults
        timeout = int(os.getenv(f"{name.upper()}_TIMEOUT", 20))
        logging.info(f"Setting {name} scraper timeout to {timeout} seconds")
        task = asyncio.create_task(scrape_with_timeout(scraper, job_request, name, timeout=timeout))
        tasks.append(task)
    
    # Use a slightly longer timeout for the gather operation
    try:
        job_results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logging.error(f"Error gathering scraper results: {str(e)}")
        job_results = [Exception(f"Gather error: {str(e)}") for _ in tasks]
    
    # Handle potential exceptions and flatten the list of jobs
    all_jobs = []
    
    for i, result in enumerate(job_results):
        source_name = list(app_state["scrapers"].keys())[i]
        if isinstance(result, Exception):
            logging.error(f"Error in {source_name} scraper: {str(result)}")
        else:
            if result:  # If we got jobs
                logging.info(f"Found {len(result)} jobs from {source_name}")
                all_jobs.extend(result)
            else:
                logging.warning(f"No jobs found from {source_name}")
    
    return all_jobs

# Add this helper function for LLM processing
async def _process_with_llm(jobs: List[Job], job_request: JobSearchRequest) -> List[Job]:
    """Process jobs with LLM with timeout handling"""
    # Filter jobs for relevance using LLM
    if app_state["llm_processor"]:
        try:
            # Set a short timeout for LLM processing
            relevant_jobs = await asyncio.wait_for(
                app_state["llm_processor"].filter_jobs_by_relevance(jobs, job_request),
                timeout=10  # 10-second timeout for LLM
            )
            return relevant_jobs
        except asyncio.TimeoutError:
            logging.error("LLM processing timed out")
            # On timeout, just return top jobs without filtering
            return jobs[:15]
        except Exception as e:
            logging.error(f"Error in LLM processing: {str(e)}")
            # On error, just return jobs without filtering
            return jobs[:15]
    else:
        # If LLM processor is not available, return jobs directly
        return jobs[:15]

async def scrape_with_timeout(scraper, job_request, source_name, timeout=20):
    """Run a scraper with a timeout to prevent hanging"""
    try:
        return await asyncio.wait_for(scraper.scrape(job_request), timeout=timeout)
    except asyncio.TimeoutError:
        logging.error(f"Scraper {source_name} timed out after {timeout} seconds")
        return Exception(f"Timeout after {timeout} seconds")

async def refresh_job_data(job_request: JobSearchRequest, cache_key: str):
    """Background task to refresh job data after initial response with mock data"""
    try:
        logging.info(f"Background task: Refreshing job data for {cache_key}")
        
        # Wait a bit before trying again
        await asyncio.sleep(5)
        
        # Ensure we have scrapers
        if not app_state["scrapers"]:
            logging.error("No scrapers available for background task")
            return
        
        # Try to get real data again with different parameters
        tasks = []
        
        # Try each scraper with modified parameters
        for name, scraper in app_state["scrapers"].items():
            # Clone the job request but with slight modifications to avoid same blocking
            modified_request = JobSearchRequest(
                position=job_request.position,
                experience=job_request.experience,
                salary=job_request.salary,
                jobNature=job_request.jobNature,
                location=job_request.location,
                skills=job_request.skills
            )
            
            # Longer timeout for LinkedIn
            timeout = 45 if name == "LinkedIn" else 25
            
            # Wrap with timeout
            task = asyncio.create_task(scrape_with_timeout(scraper, modified_request, name, timeout=timeout))
            tasks.append(task)
        
        # Run scrapers in parallel with a overall timeout
        try:
            job_results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=60)
        except asyncio.TimeoutError:
            logging.error("Background task: Overall scraping operation timed out")
            job_results = [Exception("Timeout") for _ in tasks]
        
        # Process results
        all_jobs = []
        for i, result in enumerate(job_results):
            if not isinstance(result, Exception) and result:
                all_jobs.extend(result)
        
        # If we got real jobs, update the cache
        if all_jobs:
            logging.info(f"Background task: Found {len(all_jobs)} real jobs to update cache")
            
            # Filter for relevance if LLM processor is available
            if app_state["llm_processor"]:
                try:
                    relevant_jobs = await asyncio.wait_for(
                        app_state["llm_processor"].filter_jobs_by_relevance(all_jobs, job_request),
                        timeout=15  # 15-second timeout for LLM
                    )
                except asyncio.TimeoutError:
                    logging.error("Background task: LLM processing timed out")
                    relevant_jobs = all_jobs[:15]
            else:
                relevant_jobs = all_jobs[:15]
            
            # Update cache
            app_state["job_cache"][cache_key] = {
                "timestamp": time.time(),
                "jobs": relevant_jobs
            }
            
            logging.info(f"Background task: Cache updated with {len(relevant_jobs)} relevant jobs")
        else:
            logging.warning("Background task: Failed to get real jobs, keeping empty results")
    
    except Exception as e:
        logging.error(f"Background task error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
