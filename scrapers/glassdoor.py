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

class GlassdoorScraper(BaseScraper):
    """Glassdoor job scraper implementation using requests instead of Selenium to avoid Windows errors"""
    
    def __init__(self):
        super().__init__()
        self.name = "Glassdoor"
        self.base_url = "https://www.glassdoor.com/Job/jobs.htm"
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
        
        # Format the search query
        query = quote(job_request.position)
        
        # Get location code (try to extract city name)
        location = job_request.location.split(',')[0].strip() if job_request.location else ""
        location_param = f"&sc.keyword={query}&locT=C&locId=0&locKeyword={quote(location)}"
        
        # Construct the URL
        url = f"{self.base_url}?sc.keyword={query}{location_param}"
        
        logging.info(f"Glassdoor URL: {url}")
        
        jobs = []
        
        try:
            # Make the request
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Parse the content
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Check for cookies/login modal and log it
            if soup.select(".modal_closeIcon") or soup.select(".modal"):
                logging.warning("Glassdoor has a modal that would need to be closed (login/cookies)")
            
            # Find job listings - Glassdoor has several possible DOM structures
            job_cards = soup.select(".JobsList_jobListItem__JBBUV") or \
                       soup.select("[data-test='jobListing']") or \
                       soup.select(".react-job-listing")
            
            logging.info(f"Found {len(job_cards)} Glassdoor job cards")
            
            # Process job listings
            for job_card in job_cards[:15]:  # Limit to 15 results
                try:
                    # Extract job title
                    job_title_element = job_card.select_one(".JobCard_jobTitle__RiMJv") or \
                                      job_card.select_one("[data-test='job-title']") or \
                                      job_card.select_one("a.jobLink")
                    
                    job_title = self.clean_text(job_title_element.get_text()) if job_title_element else "Unknown Title"
                    
                    # Extract job link
                    job_link = None
                    if job_title_element and job_title_element.name == "a" and job_title_element.has_attr("href"):
                        job_link = job_title_element["href"]
                        if job_link.startswith("/"):
                            job_link = f"https://www.glassdoor.com{job_link}"
                    else:
                        # Try to find link elsewhere
                        link_element = job_card.select_one("a.jobLink") or job_card.select_one("a[data-test='job-link']")
                        if link_element and link_element.has_attr("href"):
                            job_link = link_element["href"]
                            if job_link.startswith("/"):
                                job_link = f"https://www.glassdoor.com{job_link}"
                    
                    # Extract company name
                    company_element = job_card.select_one("[data-test='employerName']") or \
                                    job_card.select_one(".EmployerProfile_employerName__Xemli") or \
                                    job_card.select_one(".jobCard-company")
                    
                    company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
                    
                    # Extract location
                    location_element = job_card.select_one("[data-test='location']") or \
                                     job_card.select_one(".JobDetails_location__MbnIM") or \
                                     job_card.select_one(".location")
                    
                    location = self.clean_text(location_element.get_text()) if location_element else None
                    
                    # Extract salary if available
                    salary_element = job_card.select_one("[data-test='detailSalary']") or \
                                   job_card.select_one(".JobDetails_salaryEstimate__hqBuQ") or \
                                   job_card.select_one(".salary-estimate")
                    
                    salary = self.clean_text(salary_element.get_text()) if salary_element else None
                    
                    # Extract job nature and description - will need to get the job detail page
                    description = ""
                    job_nature = None
                    experience = None
                    
                    if job_link:
                        try:
                            # Add a small delay to avoid rate limiting
                            time.sleep(random.uniform(1, 3))
                            
                            # Fetch job details page
                            job_response = requests.get(job_link, headers=self.headers, timeout=30)
                            if job_response.status_code == 200:
                                job_soup = BeautifulSoup(job_response.text, "html.parser")
                                
                                # Extract job description
                                description_element = job_soup.select_one(".JobDetails_jobDescription__6VeZx") or \
                                                    job_soup.select_one("[data-test='jobDescriptionText']") or \
                                                    job_soup.select_one(".desc")
                                
                                if description_element:
                                    description = self.clean_text(description_element.get_text())
                                
                                # Look for job type
                                job_info_elements = job_soup.select(".JobDetails_jobInfoItem__DJDHZ") or \
                                                  job_soup.select("[data-test='job-info']") or \
                                                  job_soup.select(".empInfo")
                                
                                for element in job_info_elements:
                                    text = element.get_text().lower()
                                    if any(job_type in text for job_type in ["full-time", "part-time", "contract", "remote", "onsite", "hybrid"]):
                                        job_nature = self.clean_text(element.get_text())
                                        break
                                
                                # Try to find job nature in description if not found above
                                if not job_nature and description:
                                    if "remote" in description.lower():
                                        job_nature = "Remote"
                                    elif "on-site" in description.lower() or "onsite" in description.lower():
                                        job_nature = "Onsite"
                                    elif "hybrid" in description.lower():
                                        job_nature = "Hybrid"
                                
                                # Try to extract experience requirement from description
                                if description:
                                    exp_patterns = [
                                        r'(\d+\+?\s*(?:years|yrs)(?:\s*of)?\s*experience)',
                                        r'(\d+\s*-\s*\d+\s*(?:years|yrs)(?:\s*of)?\s*experience)'
                                    ]
                                    
                                    for pattern in exp_patterns:
                                        exp_match = re.search(pattern, description, re.IGNORECASE)
                                        if exp_match:
                                            experience = exp_match.group(1)
                                            break
                        
                        except Exception as e:
                            logging.error(f"Error fetching Glassdoor job details: {str(e)}")
                    
                    # Create job object
                    if job_link:
                        job = Job(
                            job_title=job_title,
                            company=company,
                            location=location,
                            experience=experience,
                            jobNature=job_nature,
                            salary=salary,
                            apply_link=job_link,
                            source="Glassdoor",
                            description=description
                        )
                        
                        jobs.append(job)
                
                except Exception as e:
                    logging.error(f"Error extracting Glassdoor job details: {str(e)}")
        
        except Exception as e:
            logging.error(f"Glassdoor scraping error: {str(e)}")
        
        return jobs
