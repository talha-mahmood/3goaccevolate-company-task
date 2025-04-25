from typing import List
import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote

from scrapers.base import BaseScraper
from models.job import Job
from models.request import JobSearchRequest

class IndeedScraper(BaseScraper):
    """Indeed job scraper implementation"""
    
    def __init__(self):
        super().__init__()
        self.name = "Indeed"
        self.base_url = "https://www.indeed.com/jobs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
    
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Scrape Indeed for jobs matching the request criteria
        
        Args:
            job_request: Job search criteria
            
        Returns:
            List of Job objects from Indeed
        """
        logging.info(f"Scraping Indeed for: {job_request.position}")
        
        # Format the search query
        query = self.format_search_query(job_request)
        encoded_query = quote(query)
        
        # Construct the URL
        location_param = quote(job_request.location) if job_request.location else ""
        url = f"{self.base_url}?q={encoded_query}&l={location_param}"
        
        jobs = []
        
        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.select(".jobsearch-ResultsList .cardOutline")
                
                # Process first 15 job listings
                for job_card in job_cards[:15]:
                    try:
                        # Extract job title and link
                        job_title_element = job_card.select_one("h2.jobTitle a")
                        if not job_title_element:
                            job_title_element = job_card.select_one("h2.jobTitle")
                        
                        job_title = self.clean_text(job_title_element.get_text()) if job_title_element else "Unknown Title"
                        
                        # Get job link
                        job_link_element = job_card.select_one("h2.jobTitle a")
                        job_id = None
                        
                        if job_link_element and job_link_element.has_attr("data-jk"):
                            job_id = job_link_element["data-jk"]
                        elif job_link_element and job_link_element.has_attr("href"):
                            job_id = job_link_element["href"].split("jk=")[1].split("&")[0] if "jk=" in job_link_element["href"] else None
                        
                        job_link = f"https://www.indeed.com/viewjob?jk={job_id}" if job_id else None
                        
                        # Extract company name
                        company_element = job_card.select_one("[data-testid='company-name']")
                        company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
                        
                        # Extract location
                        location_element = job_card.select_one("[data-testid='text-location']")
                        location = self.clean_text(location_element.get_text()) if location_element else None
                        
                        # Extract salary if available
                        salary_element = job_card.select_one("[data-testid='attribute_snippet_testid']")
                        salary = self.clean_text(salary_element.get_text()) if salary_element and "$" in salary_element.get_text() else None
                        
                        # Extract job type/nature
                        job_type_elements = job_card.select("[data-testid='attribute_snippet_testid']")
                        job_nature = None
                        
                        for element in job_type_elements:
                            text = element.get_text().lower()
                            if any(keyword in text for keyword in ["full-time", "part-time", "remote", "contract", "permanent", "onsite", "hybrid"]):
                                job_nature = self.clean_text(element.get_text())
                                break
                        
                        # Get detailed job description if we have a job ID
                        description = ""
                        if job_id:
                            # Make a request to the job detail page
                            detail_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                            detail_response = await client.get(detail_url, timeout=30.0)
                            
                            if detail_response.status_code == 200:
                                detail_soup = BeautifulSoup(detail_response.text, "html.parser")
                                
                                # Extract job description
                                description_element = detail_soup.select_one("#jobDescriptionText")
                                if description_element:
                                    description = self.clean_text(description_element.get_text())
                                
                                # Try to extract experience requirement from description
                                experience = None
                                if description:
                                    experience_indicators = [
                                        "years of experience", 
                                        "years experience",
                                        "yrs experience",
                                        "years' experience"
                                    ]
                                    
                                    for indicator in experience_indicators:
                                        if indicator in description.lower():
                                            # Extract sentence containing experience info
                                            sentences = description.split('.')
                                            for sentence in sentences:
                                                if indicator in sentence.lower():
                                                    experience = sentence.strip()
                                                    break
                                            
                                            if experience:
                                                break
                        
                        # Create job object
                        if job_link:  # Only add jobs with valid links
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                salary=salary,
                                jobNature=job_nature,
                                experience=experience,
                                apply_link=job_link,
                                source="Indeed",
                                description=description
                            )
                            
                            jobs.append(job)
                    
                    except Exception as e:
                        logging.error(f"Error extracting Indeed job details: {str(e)}")
                        continue
        
        except Exception as e:
            logging.error(f"Indeed scraping error: {str(e)}")
        
        return jobs
