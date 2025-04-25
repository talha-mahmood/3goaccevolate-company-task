from typing import List
import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import quote
import time

from scrapers.base import BaseScraper
from models.job import Job
from models.request import JobSearchRequest

class GlassdoorScraper(BaseScraper):
    """Glassdoor job scraper implementation"""
    
    def __init__(self):
        super().__init__()
        self.name = "Glassdoor"
        self.base_url = "https://www.glassdoor.com/Job/jobs.htm?sc.keyword="
    
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
        
        # Construct the URL - Glassdoor needs special handling for location
        location_param = ""
        if job_request.location:
            # Extract just the city name
            city = job_request.location.split(',')[0].strip()
            location_param = f"&locT=C&locId=0&locKeyword={quote(city)}"
        
        url = f"{self.base_url}{encoded_query}{location_param}"
        
        jobs = []
        
        try:
            # Initialize the webdriver
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            # Navigate to the Glassdoor jobs page
            driver.get(url)
            
            # Handle login popup if it appears
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".modal_closeIcon"))
                )
                close_button = driver.find_element(By.CSS_SELECTOR, ".modal_closeIcon")
                close_button.click()
                time.sleep(1)
            except (TimeoutException, NoSuchElementException):
                pass  # No popup or couldn't find close button
            
            # Wait for job listings to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".JobsList_jobListItem__JBBUV"))
            )
            
            # Get job listings
            job_listings = driver.find_elements(By.CSS_SELECTOR, ".JobsList_jobListItem__JBBUV")
            
            # Process up to 15 job listings
            for i, job_item in enumerate(job_listings[:15]):
                try:
                    # Click on the job to load its details
                    job_item.click()
                    time.sleep(2)  # Wait for job details to load
                    
                    # Get job details
                    try:
                        job_title_element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".JobDetails_jobTitle__Rw_gn"))
                        )
                        job_title = self.clean_text(job_title_element.text)
                    except:
                        job_title = "Unknown Title"
                    
                    try:
                        company_element = driver.find_element(By.CSS_SELECTOR, ".EmployerProfile_employerName__Xemli")
                        company = self.clean_text(company_element.text)
                    except:
                        company = "Unknown Company"
                    
                    try:
                        location_element = driver.find_element(By.CSS_SELECTOR, ".JobDetails_location__MbnIM")
                        location = self.clean_text(location_element.text)
                    except:
                        location = None
                    
                    # Get salary if available
                    try:
                        salary_element = driver.find_element(By.CSS_SELECTOR, ".JobDetails_salaryEstimate__hqBuQ")
                        salary = self.clean_text(salary_element.text)
                    except:
                        salary = None
                    
                    # Get job description
                    try:
                        description_element = driver.find_element(By.CSS_SELECTOR, ".JobDetails_jobDescription__6VeZx")
                        description = self.clean_text(description_element.text)
                    except:
                        description = ""
                    
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
                    
                    # Get job nature
                    job_nature = None
                    job_nature_indicators = ["full-time", "part-time", "contract", "remote", "onsite", "hybrid"]
                    
                    try:
                        job_info_elements = driver.find_elements(By.CSS_SELECTOR, ".JobDetails_jobInfoItem__DJDHZ")
                        for element in job_info_elements:
                            text = element.text.lower()
                            if any(indicator in text for indicator in job_nature_indicators):
                                job_nature = self.clean_text(element.text)
                                break
                    except:
                        pass
                    
                    # Get apply link
                    try:
                        apply_button = driver.find_element(By.CSS_SELECTOR, "a[data-test='applyButton']")
                        apply_link = apply_button.get_attribute("href")
                    except:
                        try:
                            # Get the current URL as a fallback
                            apply_link = driver.current_url
                        except:
                            apply_link = f"https://www.glassdoor.com/job-listing/{job_title.lower().replace(' ', '-')}"
                    
                    # Create job object
                    job = Job(
                        job_title=job_title,
                        company=company,
                        location=location,
                        experience=experience,
                        jobNature=job_nature,
                        salary=salary,
                        apply_link=apply_link,
                        source="Glassdoor",
                        description=description
                    )
                    
                    jobs.append(job)
                
                except Exception as e:
                    logging.error(f"Error extracting Glassdoor job details: {str(e)}")
                    continue
                
        except Exception as e:
            logging.error(f"Glassdoor scraping error: {str(e)}")
        
        finally:
            if 'driver' in locals():
                driver.quit()
        
        return jobs
