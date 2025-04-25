from abc import ABC, abstractmethod
from typing import List
from models.job import Job
from models.request import JobSearchRequest

class BaseScraper(ABC):
    """Base class for job scrapers"""
    
    def __init__(self):
        self.name = "base"
    
    @abstractmethod
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Scrape jobs based on request parameters
        
        Args:
            job_request: The search criteria
            
        Returns:
            List of Job objects
        """
        pass
    
    def format_search_query(self, job_request: JobSearchRequest) -> str:
        """
        Format job request into a search query string
        
        Args:
            job_request: The search criteria
            
        Returns:
            Formatted search query
        """
        query_parts = [
            job_request.position,
            job_request.jobNature,
            job_request.location
        ]
        return " ".join([part for part in query_parts if part])
    
    def clean_text(self, text: str) -> str:
        """
        Clean scraped text by removing extra whitespace
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        return " ".join(text.split())
