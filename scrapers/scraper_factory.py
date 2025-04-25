import os
from typing import Dict, List
import logging

from scrapers.base import BaseScraper
from scrapers.linkedin import LinkedInScraper
from scrapers.indeed import IndeedScraper
from scrapers.glassdoor import GlassdoorScraper
from scrapers.mock_scraper import MockScraper

class ScraperFactory:
    """Factory class for creating job scrapers"""
    
    @staticmethod
    def create_scrapers() -> Dict[str, BaseScraper]:
        """
        Create and return all available scrapers
        
        Returns:
            Dictionary of scrapers keyed by name
        """
        use_mock = os.getenv("USE_MOCK_SCRAPERS", "False").lower() == "true"
        
        scrapers = {}
        
        if use_mock:
            logging.info("Using mock scrapers for job data")
            scrapers["LinkedIn"] = MockScraper("LinkedIn")
            scrapers["Indeed"] = MockScraper("Indeed")
            scrapers["Glassdoor"] = MockScraper("Glassdoor")
        else:
            logging.info("Using real scrapers for job data")
            try:
                scrapers["LinkedIn"] = LinkedInScraper()
            except Exception as e:
                logging.error(f"Failed to initialize LinkedIn scraper: {str(e)}")
                scrapers["LinkedIn"] = MockScraper("LinkedIn")
            
            try:
                scrapers["Indeed"] = IndeedScraper()
            except Exception as e:
                logging.error(f"Failed to initialize Indeed scraper: {str(e)}")
                scrapers["Indeed"] = MockScraper("Indeed")
            
            try:
                scrapers["Glassdoor"] = GlassdoorScraper()
            except Exception as e:
                logging.error(f"Failed to initialize Glassdoor scraper: {str(e)}")
                scrapers["Glassdoor"] = MockScraper("Glassdoor")
        
        return scrapers
