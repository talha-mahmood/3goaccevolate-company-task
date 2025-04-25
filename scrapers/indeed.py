from typing import List
import asyncio
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote
import json

from scrapers.base import BaseScraper
from scrapers.anti_blocking import get_session
from models.job import Job
from models.request import JobSearchRequest

class IndeedScraper(BaseScraper):
    """Indeed job scraper implementation - optimized for performance"""
    
    def __init__(self):
        super().__init__()
        self.name = "Indeed"
        self.base_url = "https://www.indeed.com/jobs"
    
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Scrape Indeed for jobs matching the request criteria
        
        Args:
            job_request: Job search criteria
            
        Returns:
            List of Job objects from Indeed
        """
        logging.info(f"Scraping Indeed for: {job_request.position}")
        
        # This will be run in a thread to avoid blocking
        return await asyncio.to_thread(self._scrape_indeed, job_request)
    
    def _scrape_indeed(self, job_request: JobSearchRequest) -> List[Job]:
        """Internal method to handle the actual scraping with anti-blocking measures"""
        
        # Format the search query
        query = quote(job_request.position)
        
        # Construct the URL
        location_param = quote(job_request.location) if job_request.location else ""
        url = f"{self.base_url}?q={query}&l={location_param}"
        
        logging.info(f"Indeed URL: {url}")
        
        jobs = []
        
        try:
            # Get an anti-blocking session for Indeed
            session = get_session("Indeed")
            
            # Make the request with our anti-blocking session
            response = session.get(url, timeout=10)  # Use a shorter timeout
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try different selectors for job cards (Indeed changes their structure frequently)
                job_cards = soup.select(".jobsearch-ResultsList .cardOutline")
                if not job_cards:
                    job_cards = soup.select(".job_seen_beacon")
                if not job_cards:
                    job_cards = soup.select("[data-testid='jobListing']")
                if not job_cards:
                    job_cards = soup.select(".resultWithShelf")
                
                logging.info(f"Found {len(job_cards)} Indeed job cards")
                
                # If we found jobs, process them (limit to 10 to avoid taking too long)
                if job_cards:
                    for job_card in job_cards[:10]:
                        try:
                            # Extract basic job information (minimal processing)
                            
                            # Extract job title
                            job_title_element = (
                                job_card.select_one("h2.jobTitle a") or
                                job_card.select_one("h2.jobTitle") or
                                job_card.select_one("[data-testid='jobTitle']") or
                                job_card.select_one("a.jcs-JobTitle") or
                                job_card.select_one(".jobTitle")
                            )
                            
                            job_title = self.clean_text(job_title_element.get_text()) if job_title_element else "Unknown Title"
                            
                            # Get job link
                            job_link_element = (
                                job_card.select_one("h2.jobTitle a") or
                                job_card.select_one("a[data-testid='jobLink']") or
                                job_card.select_one("a.jcs-JobTitle") or
                                job_card.select_one("a.resultContent")
                            )
                            
                            job_id = None
                            job_link = None
                            
                            if job_link_element:
                                if job_link_element.has_attr("href"):
                                    href = job_link_element["href"]
                                    if href.startswith("/"):
                                        job_link = f"https://www.indeed.com{href}"
                                    else:
                                        job_link = href
                                elif job_link_element.has_attr("data-jk"):
                                    job_id = job_link_element["data-jk"]
                                    job_link = f"https://www.indeed.com/viewjob?jk={job_id}"
                            
                            # Extract company name
                            company_element = (
                                job_card.select_one("[data-testid='company-name']") or
                                job_card.select_one(".companyName") or
                                job_card.select_one(".company") or
                                job_card.select_one(".companyInfo")
                            )
                            
                            company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
                            
                            # Extract location
                            location_element = (
                                job_card.select_one("[data-testid='text-location']") or
                                job_card.select_one(".companyLocation") or
                                job_card.select_one(".location")
                            )
                            
                            location = self.clean_text(location_element.get_text()) if location_element else None
                            
                            # Extract minimal info first, don't fetch full details to save time
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,  # Will be populated by LLM if needed
                                jobNature=None,   # Will be populated by LLM if needed
                                salary=None,      # Will be populated by LLM if needed
                                apply_link=job_link if job_link else f"https://www.indeed.com/jobs?q={query}",
                                source="Indeed",
                                description=f"Job listing for {job_title} at {company} in {location if location else 'unknown location'}."
                            )
                            
                            jobs.append(job)
                        
                        except Exception as e:
                            logging.error(f"Error extracting Indeed job details: {str(e)}")
                            continue
            else:
                logging.error(f"Indeed returned status code {response.status_code}")
        
        except Exception as e:
            logging.error(f"Indeed scraper error: {str(e)}")
        
        if not jobs:
            logging.warning("No jobs found from Indeed.")
        
        return jobs
