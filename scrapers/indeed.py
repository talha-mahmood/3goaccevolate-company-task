from typing import List
import asyncio
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote, urlencode
import json
import time
import random
import requests
import re

from scrapers.base import BaseScraper
from scrapers.anti_blocking import get_session
from models.job import Job
from models.request import JobSearchRequest

class IndeedScraper(BaseScraper):
    """Indeed job scraper implementation with advanced anti-blocking"""
    
    def __init__(self):
        super().__init__()
        self.name = "Indeed"
        self.base_url = "https://www.indeed.com/jobs"
        self.mobile_url = "https://www.indeed.com/m/jobs"
        self.api_url = "https://www.indeed.com/jobs/api/search"
        
        # Realistic browser headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "DNT": "1",
            "Cache-Control": "max-age=0",
            "TE": "trailers"
        }
        
        # Mobile headers
        self.mobile_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
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
        
        # This will be run in a thread to avoid blocking
        return await asyncio.to_thread(self._scrape_indeed, job_request)
    
    def _scrape_indeed(self, job_request: JobSearchRequest) -> List[Job]:
        """Internal method to handle the actual scraping with anti-blocking measures"""
        jobs = []
        
        # Try multiple scraping approaches in sequence until we get results
        scraping_methods = [
            self._scrape_standard_site,
            self._scrape_mobile_site,
            self._scrape_api_endpoint,
            self._scrape_with_direct_requests
        ]
        
        for method in scraping_methods:
            try:
                method_jobs = method(job_request)
                if method_jobs:
                    jobs.extend(method_jobs)
                    logging.info(f"Successfully scraped {len(method_jobs)} jobs using {method.__name__}")
                    break
            except Exception as e:
                logging.error(f"Error in Indeed scraping method {method.__name__}: {str(e)}")
                continue
        
        if not jobs:
            logging.warning("No jobs found from Indeed after trying all methods.")
        
        return jobs
    
    def _scrape_standard_site(self, job_request: JobSearchRequest) -> List[Job]:
        """Scrape Indeed's standard website"""
        # Format the search query
        query = quote(job_request.position)
        
        # Construct the URL with more parameters to look legitimate
        params = {
            "q": job_request.position,
            "l": job_request.location if job_request.location else "",
            "sort": "date",  # Sort by date to get newest
            "fromage": "7",  # Last 7 days
            "radius": "25",  # 25 mile radius
            "filter": "0"    # No filters
        }
        
        url = f"{self.base_url}?{urlencode(params)}"
        logging.info(f"Indeed URL: {url}")
        
        jobs = []
        
        try:
            # Random delay to avoid patterns
            time.sleep(random.uniform(1, 3))
            
            # Use direct requests with custom headers
            response = requests.get(
                url,
                headers=self.headers,
                timeout=15,
                cookies={"indeed_preferred": "VIS"}  # Set indeed_preferred cookie
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try different selectors for job cards
                job_cards = (
                    soup.select(".jobsearch-ResultsList .cardOutline") or
                    soup.select(".job_seen_beacon") or
                    soup.select("[data-testid='jobListing']") or
                    soup.select(".resultWithShelf") or
                    soup.select(".job_result") or
                    soup.select(".jobCard")
                )
                
                logging.info(f"Found {len(job_cards)} Indeed job cards (standard site)")
                
                # Process job listings (limited to first 10)
                for i, job_card in enumerate(job_cards[:10]):
                    try:
                        job = self._extract_job_from_card(job_card, job_request)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting job {i+1}: {str(e)}")
            else:
                logging.error(f"Indeed returned status code {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error in standard Indeed scraper: {str(e)}")
            raise
        
        return jobs
    
    def _scrape_mobile_site(self, job_request: JobSearchRequest) -> List[Job]:
        """Scrape Indeed's mobile website which often has simpler anti-bot measures"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        url = f"{self.mobile_url}?q={query}&l={location}"
        logging.info(f"Indeed mobile URL: {url}")
        
        jobs = []
        
        try:
            # Random delay between requests
            time.sleep(random.uniform(2, 4))
            
            # Use direct requests with mobile headers
            response = requests.get(
                url,
                headers=self.mobile_headers,
                timeout=15
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Mobile site has different selectors
                job_cards = (
                    soup.select(".jobCard") or
                    soup.select(".jobsearch-ResultsList li") or
                    soup.select(".tapItem")
                )
                
                logging.info(f"Found {len(job_cards)} Indeed job cards (mobile site)")
                
                for job_card in job_cards[:10]:
                    try:
                        # Extract basic job info
                        title_elem = job_card.select_one("h2.jobTitle") or job_card.select_one("h2")
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else "Unknown Title"
                        
                        # Get company name
                        company_elem = job_card.select_one(".companyName") or job_card.select_one(".company")
                        company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                        
                        # Get location
                        location_elem = job_card.select_one(".companyLocation") or job_card.select_one(".location")
                        location = self.clean_text(location_elem.get_text()) if location_elem else None
                        
                        # Get link
                        link_elem = job_card.select_one("a") or title_elem.parent if title_elem else None
                        job_link = None
                        
                        if link_elem and link_elem.has_attr("href"):
                            href = link_elem["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.indeed.com{href}"
                            else:
                                job_link = href
                        else:
                            # Try to find job ID
                            job_id_match = re.search(r'jobId[=":]+([^"&]+)', str(job_card))
                            if job_id_match:
                                job_id = job_id_match.group(1)
                                job_link = f"https://www.indeed.com/viewjob?jk={job_id}"
                        
                        if job_title and company and job_link:
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link,
                                source="Indeed",
                                description=f"Job listing for {job_title} at {company} in {location if location else 'unknown location'}.",
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting Indeed mobile job: {str(e)}")
            else:
                logging.error(f"Indeed mobile site returned status code {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error in mobile Indeed scraper: {str(e)}")
            raise
        
        return jobs
    
    def _scrape_api_endpoint(self, job_request: JobSearchRequest) -> List[Job]:
        """Try to scrape using Indeed's API endpoint (if available)"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        api_url = f"{self.api_url}?q={query}&l={location}"
        logging.info(f"Indeed API URL: {api_url}")
        
        jobs = []
        
        try:
            # Random delay
            time.sleep(random.uniform(2, 5))
            
            # Add additional headers that might be expected by the API
            api_headers = self.headers.copy()
            api_headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest"
            })
            
            response = requests.get(
                api_url,
                headers=api_headers,
                timeout=15
            )
            
            if response.status_code == 200 and 'application/json' in response.headers.get('Content-Type', ''):
                try:
                    data = response.json()
                    api_jobs = data.get("results", [])
                    
                    for job_data in api_jobs[:10]:
                        try:
                            job_title = job_data.get("title", "Unknown Title")
                            company = job_data.get("company", "Unknown Company")
                            location = job_data.get("formattedLocation", job_data.get("location"))
                            job_link = job_data.get("url")
                            
                            if job_link and not job_link.startswith("http"):
                                job_link = f"https://www.indeed.com{job_link}"
                            
                            if job_title and company and job_link:
                                job = Job(
                                    job_title=job_title,
                                    company=company,
                                    location=location,
                                    experience=None,
                                    jobNature=None,
                                    salary=None,
                                    apply_link=job_link,
                                    source="Indeed",
                                    description=job_data.get("snippet", f"Job listing for {job_title} at {company}"),
                                    relevance_score=75
                                )
                                jobs.append(job)
                        except Exception as e:
                            logging.error(f"Error processing API job data: {str(e)}")
                except json.JSONDecodeError:
                    logging.error("Failed to parse Indeed API JSON response")
            else:
                logging.error(f"Indeed API returned status code {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error in Indeed API scraper: {str(e)}")
            raise
        
        return jobs
    
    def _scrape_with_direct_requests(self, job_request: JobSearchRequest) -> List[Job]:
        """Last resort method that tries different request patterns"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Add some randomization to the URL to avoid pattern detection
        timestamp = int(time.time())
        random_param = random.randint(1000, 9999)
        
        url = f"https://www.indeed.com/jobs?q={query}&l={location}&sort=date&ts={timestamp}&r={random_param}"
        logging.info(f"Indeed direct URL: {url}")
        
        jobs = []
        
        try:
            # Use a completely different set of headers
            headers = {
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(90, 114)}.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache"
            }
            
            # Add referrer from a search engine
            headers["Referer"] = random.choice([
                "https://www.google.com/search?q=jobs",
                "https://www.bing.com/search?q=indeed+jobs",
                "https://duckduckgo.com/?q=job+search"
            ])
            
            # Simulate a real browser session with cookies
            session = requests.Session()
            
            # First visit the Indeed homepage to get cookies
            time.sleep(random.uniform(1, 3))
            session.get("https://www.indeed.com/", headers=headers, timeout=10)
            
            # Then visit the search page
            time.sleep(random.uniform(2, 5))
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try different selectors for job cards
                job_cards = (
                    soup.select(".jobsearch-ResultsList .cardOutline") or
                    soup.select(".job_seen_beacon") or
                    soup.select("[data-testid='jobListing']") or
                    soup.select(".resultWithShelf") or
                    soup.select(".tapItem")
                )
                
                logging.info(f"Found {len(job_cards)} Indeed job cards (direct requests)")
                
                # Extract jobs
                for job_card in job_cards[:10]:
                    try:
                        job = self._extract_job_from_card(job_card, job_request)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting job from direct request: {str(e)}")
            else:
                logging.error(f"Indeed direct request returned status code {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error in direct Indeed scraper: {str(e)}")
            raise
        
        return jobs
    
    def _extract_job_from_card(self, job_card, job_request):
        """Helper function to extract job details from a card"""
        # Extract job title
        job_title_element = (
            job_card.select_one("h2.jobTitle a") or
            job_card.select_one("h2.jobTitle") or
            job_card.select_one("[data-testid='jobTitle']") or
            job_card.select_one("a.jcs-JobTitle") or
            job_card.select_one(".jobTitle") or
            job_card.select_one("h2 a")
        )
        
        job_title = self.clean_text(job_title_element.get_text()) if job_title_element else None
        
        # Get job link
        job_link_element = (
            job_card.select_one("h2.jobTitle a") or
            job_card.select_one("a[data-testid='jobLink']") or
            job_card.select_one("a.jcs-JobTitle") or
            job_card.select_one("a.resultContent") or
            job_card.select_one("h2 a") or
            job_card.select_one("a")
        )
        
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
        else:
            # Try to find job ID in the HTML
            job_id_match = re.search(r'data-jk=["\']([^"\']+)', str(job_card))
            if job_id_match:
                job_id = job_id_match.group(1)
                job_link = f"https://www.indeed.com/viewjob?jk={job_id}"
        
        # Extract company name
        company_element = (
            job_card.select_one("[data-testid='company-name']") or
            job_card.select_one(".companyName") or
            job_card.select_one(".company") or
            job_card.select_one(".companyInfo") or
            job_card.select_one("span.company")
        )
        
        company = self.clean_text(company_element.get_text()) if company_element else "Unknown Company"
        
        # Extract location
        location_element = (
            job_card.select_one("[data-testid='text-location']") or
            job_card.select_one(".companyLocation") or
            job_card.select_one(".location") or
            job_card.select_one(".accessible-contrast-color-location")
        )
        
        location = self.clean_text(location_element.get_text()) if location_element else None
        
        # If we have the minimum required info, create a job object
        if job_title and job_link and company:
            job = Job(
                job_title=job_title,
                company=company,
                location=location,
                experience=None,
                jobNature=None,
                salary=None,
                apply_link=job_link,
                source="Indeed",
                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                relevance_score=75  # Default score for Indeed jobs
            )
            return job
        
        return None
