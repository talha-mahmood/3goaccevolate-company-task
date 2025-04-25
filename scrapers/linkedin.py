from typing import List
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import time
import random
import re

from scrapers.base import BaseScraper
from models.job import Job
from models.request import JobSearchRequest

class LinkedInScraper(BaseScraper):
    """LinkedIn job scraper implementation using requests to avoid Windows errors"""
    
    def __init__(self):
        super().__init__()
        self.name = "LinkedIn"
        self.base_url = "https://www.linkedin.com/jobs/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="106", "Google Chrome";v="106", "Not;A=Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Referer": "https://www.google.com/",
        }
    
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Scrape LinkedIn for jobs matching the request criteria
        
        Args:
            job_request: Job search criteria
            
        Returns:
            List of Job objects from LinkedIn
        """
        logging.info(f"Scraping LinkedIn for: {job_request.position}")
        
        # This will be run in a thread to avoid blocking
        return await asyncio.to_thread(self._scrape_linkedin, job_request)
    
    def _scrape_linkedin(self, job_request: JobSearchRequest) -> List[Job]:
        """Internal method to handle the actual scraping with requests - optimized for performance"""
        
        # Format the search query and location
        keywords = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Format into LinkedIn URL (using their URL structure)
        url = f"{self.base_url}/?keywords={keywords}&location={location}&f_TPR=r86400&position=1&pageNum=0"
        
        logging.info(f"LinkedIn URL: {url}")
        
        jobs = []
        
        try:
            # Make the request - with a longer timeout
            start_time = time.time()
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            fetch_time = time.time() - start_time
            logging.info(f"LinkedIn fetch took {fetch_time:.2f} seconds")
            
            # Parse the content
            start_parse = time.time()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Get job cards - trying multiple selectors
            job_cards = soup.select(".jobs-search__results-list > li")
            if not job_cards:
                job_cards = soup.select("ul.jobs-search__results-list li")
            if not job_cards:
                job_cards = soup.select(".job-search-card")
                
            logging.info(f"Found {len(job_cards)} LinkedIn job cards - parsing took {time.time() - start_parse:.2f} seconds")
            
            # For debugging, check what selectors are available if no job cards found
            if not job_cards:
                logging.debug("LinkedIn HTML structure might have changed, attempting to analyze HTML")
                # Look for common job card patterns
                potential_job_elements = soup.select("li[data-occludable-job-id]")
                if potential_job_elements:
                    logging.debug(f"Found {len(potential_job_elements)} potential job elements with data-occludable-job-id")
                    job_cards = potential_job_elements
                else:
                    logging.debug("No job cards found using any selector")
            
            # Process job listings with progress logging - all in one pass to avoid timeout
            start_processing = time.time()
            for i, job_card in enumerate(job_cards[:10]):  # Limit to 10 results for better performance
                try:
                    card_start = time.time()
                    logging.debug(f"Processing LinkedIn job card {i+1}/{len(job_cards)}")
                    
                    # Extract all data from the card in one go to avoid repeated DOM traversal
                    # Extract job title and link
                    job_link_element = job_card.select_one("a.base-card__full-link") or \
                                      job_card.select_one("a.job-card-container__link") or \
                                      job_card.select_one("a[data-tracking-control-name='public_jobs_jserp-result_search-card']") or \
                                      job_card.select_one("a")
                    
                    job_title = None
                    job_link = None
                    
                    if job_link_element:
                        job_title = self.clean_text(job_link_element.get_text())
                        job_link = job_link_element.get("href")
                    
                    if not job_title:
                        title_element = job_card.select_one(".base-search-card__title") or \
                                      job_card.select_one(".job-search-card__title") or \
                                      job_card.select_one("h3") or \
                                      job_card.select_one(".base-card__full-link")
                        if title_element:
                            job_title = self.clean_text(title_element.get_text())
                    
                    # If we still don't have a title or link, skip this job
                    if not job_title or not job_link:
                        logging.debug(f"Skipping LinkedIn job {i+1} - could not extract title or link")
                        continue
                    
                    # Extract company name
                    company_element = job_card.select_one(".base-search-card__subtitle a") or \
                                     job_card.select_one(".base-search-card__subtitle") or \
                                     job_card.select_one(".job-search-card__subtitle-link") or \
                                     job_card.select_one(".job-search-card__subtitle") or \
                                     job_card.select_one("h4")
                    
                    company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
                    
                    # Extract location
                    location_element = job_card.select_one(".job-search-card__location") or \
                                      job_card.select_one(".base-search-card__metadata") or \
                                      job_card.select_one(".job-card-container__metadata-item")
                    
                    location = self.clean_text(location_element.get_text()) if location_element else None
                    
                    # Avoid detailed job page fetch to improve performance
                    job = Job(
                        job_title=job_title,
                        company=company,
                        location=location,
                        experience=None,  # Skip for now to avoid timeouts
                        jobNature=None,   # Skip for now to avoid timeouts
                        salary=None,      # LinkedIn rarely shows salary
                        apply_link=job_link,
                        source="LinkedIn",
                        description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                        relevance_score=75  # Default score for LinkedIn jobs
                    )
                    
                    jobs.append(job)
                    logging.debug(f"LinkedIn job {i+1} processed in {time.time() - card_start:.2f} seconds")
                
                except Exception as e:
                    logging.error(f"Error extracting LinkedIn job details for card {i+1}: {str(e)}")
                    continue
            
            processing_time = time.time() - start_processing
            logging.info(f"Processed {len(jobs)} LinkedIn jobs in {processing_time:.2f} seconds")
        
        except Exception as e:
            logging.error(f"LinkedIn scraping error: {str(e)}")
        
        return jobs
