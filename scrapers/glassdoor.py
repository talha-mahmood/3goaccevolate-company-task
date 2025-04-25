from typing import List
import asyncio
import logging
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlencode

from scrapers.base import BaseScraper
from scrapers.anti_blocking import get_session, clear_session
from models.job import Job
from models.request import JobSearchRequest

class GlassdoorScraper(BaseScraper):
    """Glassdoor job scraper implementation"""
    
    def __init__(self):
        super().__init__()
        self.name = "Glassdoor"
        self.base_url = "https://www.glassdoor.com/Job/jobs.htm"
        self.search_url = "https://www.glassdoor.com/Job/jobs.htm"
    
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Scrape Glassdoor for jobs matching the request criteria
        
        Args:
            job_request: Job search criteria
            
        Returns:
            List of Job objects from Glassdoor
        """
        logging.info(f"Scraping Glassdoor for: {job_request.position}")
        
        # This will be run in a thread to avoid blocking
        return await asyncio.to_thread(self._scrape_glassdoor, job_request)
    
    def _scrape_glassdoor(self, job_request: JobSearchRequest) -> List[Job]:
        """Internal method to handle the actual scraping with requests"""
        jobs = []
        
        # Try multiple approaches
        try:
            # First try the standard approach
            standard_jobs = self._scrape_standard(job_request)
            if standard_jobs:
                jobs.extend(standard_jobs)
                return jobs
            
            # If standard approach fails, try the alternate approach
            # Clear the session to get a fresh one
            clear_session("Glassdoor")
            
            alternate_jobs = self._scrape_alternate(job_request)
            if alternate_jobs:
                jobs.extend(alternate_jobs)
                return jobs
            
        except Exception as e:
            logging.error(f"Glassdoor scraping error: {str(e)}")
        
        return jobs
    
    def _scrape_standard(self, job_request: JobSearchRequest) -> List[Job]:
        """Standard scraping approach for Glassdoor"""
        # Format the search query
        position = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Construct the URL
        url = f"{self.search_url}?sc.keyword={position}&sc.keyword={position}&locT=C&locId=0&locKeyword={location}"
        
        logging.info(f"Glassdoor URL: {url}")
        
        jobs = []
        
        try:
            # Get an anti-blocking session
            session = get_session("Glassdoor")
            
            # Add special headers for Glassdoor
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.glassdoor.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1"
            }
            
            # First visit the homepage to get cookies
            session.get("https://www.glassdoor.com/", headers=headers, timeout=15)
            
            # Random delay
            time.sleep(random.uniform(2, 4))
            
            # Then get the search page
            response = session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try different selectors to find job listings
                job_cards = (
                    soup.select(".react-job-listing") or
                    soup.select(".jl") or
                    soup.select("[data-test='jobListing']") or
                    soup.select(".jobCard")
                )
                
                logging.info(f"Found {len(job_cards)} Glassdoor job cards")
                
                # Process job listings
                for job_card in job_cards[:10]:
                    try:
                        # Extract job information from the card
                        job_title_element = job_card.select_one(".jobLink") or job_card.select_one(".job-title")
                        job_title = self.clean_text(job_title_element.get_text()) if job_title_element else None
                        
                        # Get company
                        company_element = job_card.select_one("[data-test='employerName']") or job_card.select_one(".jobCompany")
                        company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
                        
                        # Get location
                        location_element = job_card.select_one("[data-test='location']") or job_card.select_one(".location")
                        location = self.clean_text(location_element.get_text()) if location_element else None
                        
                        # Get job link
                        job_link = None
                        link_element = job_card.select_one("a.jobLink") or job_card.select_one("a")
                        if link_element and link_element.has_attr("href"):
                            href = link_element["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.glassdoor.com{href}"
                            else:
                                job_link = href
                        
                        # Create job object if we have the minimum required fields
                        if job_title and job_link:
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link,
                                source="Glassdoor",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75  # Default score for Glassdoor jobs
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting Glassdoor job: {str(e)}")
            else:
                logging.error(f"Glassdoor returned status code {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error in standard Glassdoor scraper: {str(e)}")
            raise
        
        return jobs
    
    def _scrape_alternate(self, job_request: JobSearchRequest) -> List[Job]:
        """Alternative scraping approach using a different URL structure"""
        # Try a different URL format
        position = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else "United-States"
        
        url = f"https://www.glassdoor.com/Job/{location}-{position}-jobs-SRCH_IL.0,{len(location)}_{KO}{len(location)+1},{len(location)+len(position)+1}.htm"
        
        logging.info(f"Glassdoor alternate URL: {url}")
        
        jobs = []
        
        try:
            # Create a fresh session with different headers
            session = requests.Session()
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Referer": "https://www.google.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site"
            }
            
            # First visit the homepage
            session.get("https://www.glassdoor.com/", headers=headers, timeout=15)
            
            # Random delay
            time.sleep(random.uniform(3, 5))
            
            # Visit the search page
            response = session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for job cards with different selectors
                job_cards = (
                    soup.select(".jobCard") or
                    soup.select(".listing") or
                    soup.select("[data-id]") or
                    soup.select(".job-listing")
                )
                
                logging.info(f"Found {len(job_cards)} Glassdoor job cards (alternate method)")
                
                # Process each job
                for job_card in job_cards[:10]:
                    try:
                        # Extract job title
                        title_element = job_card.select_one(".job-title") or job_card.select_one(".title")
                        job_title = self.clean_text(title_element.get_text()) if title_element else None
                        
                        # Extract company
                        company_element = job_card.select_one(".employer-name") or job_card.select_one(".company")
                        company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
                        
                        # Extract location
                        location_element = job_card.select_one(".location") or job_card.select_one(".job-location")
                        location = self.clean_text(location_element.get_text()) if location_element else None
                        
                        # Extract link
                        link_element = job_card.select_one("a") or title_element.parent if title_element else None
                        job_link = None
                        
                        if link_element and link_element.has_attr("href"):
                            href = link_element["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.glassdoor.com{href}"
                            else:
                                job_link = href
                        
                        # Create job object
                        if job_title and job_link:
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link,
                                source="Glassdoor",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting Glassdoor job (alternate): {str(e)}")
            else:
                logging.error(f"Glassdoor alternate method returned status code {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error in alternate Glassdoor scraper: {str(e)}")
            raise
        
        return jobs
