from typing import List
import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import quote

from scrapers.base import BaseScraper
from models.job import Job
from models.request import JobSearchRequest

class LinkedInScraper(BaseScraper):
    """LinkedIn job scraper implementation"""
    
    def __init__(self):
        super().__init__()
        self.name = "LinkedIn"
        self.base_url = "https://www.linkedin.com/jobs/search/?keywords="
    
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
        """Internal method to handle the actual scraping with Selenium"""
        
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Format the search query
        query = self.format_search_query(job_request)
        encoded_query = quote(query)
        
        # Create location parameter if provided
        location_param = ""
        if job_request.location:
            location_param = f"&location={quote(job_request.location)}"
        
        # Construct the URL
        url = f"{self.base_url}{encoded_query}{location_param}"
        
        jobs = []
        
        try:
            # Initialize the webdriver
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Navigate to the LinkedIn jobs page
            driver.get(url)
            
            # Wait for job listings to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "jobs-search__results-list"))
            )
            
            # Scroll to load more jobs
            self._scroll_page(driver)
            
            # Parse the page content
            soup = BeautifulSoup(driver.page_source, "html.parser")
            job_listings = soup.select("ul.jobs-search__results-list > li")
            
            # Extract job information
            for job_item in job_listings[:15]:  # Limit to first 15 results
                try:
                    # Get basic job info
                    job_link_element = job_item.select_one("a.base-card__full-link")
                    job_title = self.clean_text(job_link_element.get_text()) if job_link_element else "Unknown Title"
                    job_link = job_link_element["href"] if job_link_element else ""
                    
                    company_element = job_item.select_one(".base-search-card__subtitle")
                    company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
                    
                    location_element = job_item.select_one(".job-search-card__location")
                    location = self.clean_text(location_element.get_text()) if location_element else None
                    
                    # Click on job to get description
                    if job_link:
                        # Get additional info by visiting the job page
                        driver.get(job_link)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "show-more-less-html__markup"))
                        )
                        
                        job_details_soup = BeautifulSoup(driver.page_source, "html.parser")
                        
                        # Extract job description
                        description_element = job_details_soup.select_one(".show-more-less-html__markup")
                        description = self.clean_text(description_element.get_text()) if description_element else ""
                        
                        # Extract other details if available
                        criteria_elements = job_details_soup.select(".description__job-criteria-item")
                        experience = None
                        job_nature = None
                        
                        for criterion in criteria_elements:
                            header = criterion.select_one(".description__job-criteria-subheader")
                            value = criterion.select_one(".description__job-criteria-text")
                            
                            if header and value:
                                header_text = header.get_text().strip().lower()
                                value_text = value.get_text().strip()
                                
                                if "experience" in header_text:
                                    experience = value_text
                                elif "employment type" in header_text:
                                    job_nature = value_text
                        
                        # Create job object
                        job = Job(
                            job_title=job_title,
                            company=company,
                            location=location,
                            experience=experience,
                            jobNature=job_nature,
                            salary=None,  # LinkedIn rarely shows salary
                            apply_link=job_link,
                            source="LinkedIn",
                            description=description
                        )
                        
                        jobs.append(job)
                    
                except Exception as e:
                    logging.error(f"Error extracting LinkedIn job details: {str(e)}")
                    continue
                    
        except Exception as e:
            logging.error(f"LinkedIn scraping error: {str(e)}")
        
        finally:
            if 'driver' in locals():
                driver.quit()
        
        return jobs
    
    def _scroll_page(self, driver):
        """Scroll down the page to load more job listings"""
        try:
            # Scroll down a few times to load more jobs
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                # Wait for page to load more content
                asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Error scrolling LinkedIn page: {str(e)}")
