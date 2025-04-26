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
import subprocess
import sys
import os

from scrapers.base import BaseScraper
from models.job import Job
from models.request import JobSearchRequest

class IndeedScraper(BaseScraper):
    """Indeed job scraper implementation with specialized anti-blocking techniques"""
    
    def __init__(self):
        super().__init__()
        self.name = "Indeed"
        self.base_url = "https://www.indeed.com/jobs"
        self.mobile_url = "https://www.indeed.com/m/jobs"
        self.api_url = "https://www.indeed.com/jobs/api/search"
        
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Scrape Indeed for jobs matching the request criteria
        
        Args:
            job_request: Job search criteria
            
        Returns:
            List of Job objects from Indeed
        """
        logging.info(f"Scraping Indeed for: {job_request.position}")
        
        # Use a timeout for the thread-based scraping to prevent hanging
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._scrape_indeed_with_multiple_methods, job_request),
                timeout=25  # 25 second timeout
            )
        except asyncio.TimeoutError:
            logging.error("Indeed scraper timed out after 25 seconds")
            return []
        except Exception as e:
            logging.error(f"Error in Indeed scraper: {str(e)}")
            return []
    
    def _scrape_indeed_with_multiple_methods(self, job_request: JobSearchRequest) -> List[Job]:
        """Attempt multiple scraping methods for Indeed"""
        jobs = []
        
        # Try multiple methods with various IP rotations and user agent combinations
        methods = [
            self._scrape_with_residential_proxy,  # New method first
            self._scrape_with_alternative_indeed_domains,
            self._scrape_with_special_headers,
            self._scrape_with_referer_chains,
            self._scrape_with_country_code_domains
        ]
        
        for method in methods:
            try:
                method_name = method.__name__
                logging.info(f"Trying Indeed scraping method: {method_name}")
                method_jobs = method(job_request)
                
                if method_jobs:
                    logging.info(f"Successfully found {len(method_jobs)} jobs with {method_name}")
                    jobs.extend(method_jobs)
                    break
            except Exception as e:
                logging.error(f"Error in {method.__name__}: {str(e)}")
                continue
        
        if not jobs:
            logging.warning("All Indeed scraping methods failed")
            
        return jobs
    
    def _scrape_with_residential_proxy(self, job_request: JobSearchRequest) -> List[Job]:
        """Use a residential proxy service for more reliable scraping"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        url = f"https://www.indeed.com/jobs?q={query}&l={location}&sort=date"
        logging.info(f"Trying Indeed with residential proxy: {url}")
        
        jobs = []
        
        try:
            # Create a session with extremely realistic headers
            session = requests.Session()
            
            # Use headers that exactly match a real Chrome browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Sec-Ch-Ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Instead of using actual residential proxies, create a direct request with all the right settings
            # If you want to use actual proxies, you'd replace this section with your proxy service
            
            # First, make a request to a search engine
            session.get("https://www.google.com/search?q=indeed+jobs", headers=headers, timeout=10)
            
            # Set custom cookies that mimic a real user session
            cookies = {
                "indeed_rcc": "1",
                "JSESSIONID": f"DE4C{random.randint(10000, 99999)}",
                "CTK": f"{self._generate_random_token(20)}",
                "RF": f"{self._generate_random_token(10)}",
                "PREF": f"lang=en|TM={int(time.time())}",
            }
            
            # Add the cookies to the session
            for name, value in cookies.items():
                session.cookies.set(name, value, domain=".indeed.com")
            
            # Now, make the request to Indeed with all the right cookies and headers
            headers["Referer"] = "https://www.google.com/"
            
            # Use the India domain which often has less restrictions
            india_url = f"https://in.indeed.com/jobs?q={query}&l={location}&sort=date"
            response = session.get(india_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # Try parsing the content
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for job cards
                job_cards = (
                    soup.select(".jobsearch-ResultsList .cardOutline") or
                    soup.select(".job_seen_beacon") or
                    soup.select("[data-testid='jobListing']") or
                    soup.select(".resultWithShelf") or
                    soup.select(".tapItem") or
                    soup.select("[data-resultid]") or
                    soup.select("a[data-mobtk]")
                )
                
                logging.info(f"Found {len(job_cards)} Indeed job cards with residential proxy")
                
                if not job_cards:
                    # Try to extract any job data directly from the page
                    logging.info("No job cards found, trying to extract job data directly from JSON in page")
                    
                    # Look for JSON data in the page
                    json_match = re.search(r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*({.*?});', response.text)
                    if json_match:
                        try:
                            json_data = json.loads(json_match.group(1))
                            job_results = json_data.get('metaData', {}).get('mosaicProviderJobCardsModel', {}).get('results', [])
                            
                            if job_results:
                                logging.info(f"Found {len(job_results)} jobs from JSON data")
                                
                                for job_data in job_results[:10]:
                                    try:
                                        job_title = job_data.get('title')
                                        company = job_data.get('company')
                                        job_key = job_data.get('jobkey')
                                        location = job_data.get('formattedLocation') or job_data.get('location')
                                        
                                        if job_title and company:
                                            job_link = f"https://in.indeed.com/viewjob?jk={job_key}" if job_key else None
                                            
                                            job = Job(
                                                job_title=job_title,
                                                company=company,
                                                location=location,
                                                experience=None,
                                                jobNature=None,
                                                salary=None,
                                                apply_link=job_link or india_url,
                                                source="Indeed (India)",
                                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                                relevance_score=75
                                            )
                                            jobs.append(job)
                                    except Exception as e:
                                        logging.error(f"Error extracting job from JSON: {str(e)}")
                        except Exception as e:
                            logging.error(f"Error parsing JSON data: {str(e)}")
                
                # Process regular job cards if we found any
                for job_card in job_cards[:10]:
                    try:
                        # Extract job title
                        title_elem = (
                            job_card.select_one("h2.jobTitle") or 
                            job_card.select_one(".jobTitle") or 
                            job_card.select_one("h2") or
                            job_card.select_one("a[data-mobtk]")
                        )
                        
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                        
                        # Extract company name
                        company_elem = (
                            job_card.select_one(".companyName") or 
                            job_card.select_one(".company") or
                            job_card.select_one("[data-testid='company-name']")
                        )
                        
                        company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                        
                        # Extract location
                        location_elem = (
                            job_card.select_one(".companyLocation") or 
                            job_card.select_one(".location") or
                            job_card.select_one("[data-testid='text-location']")
                        )
                        
                        location = self.clean_text(location_elem.get_text()) if location_elem else None
                        
                        # Extract job link
                        job_link = None
                        
                        # Try to extract job ID
                        job_id = None
                        if job_card.has_attr("data-jk"):
                            job_id = job_card["data-jk"]
                        elif job_card.has_attr("data-id"):
                            job_id = job_card["data-id"]
                        elif title_elem and title_elem.has_attr("data-jk"):
                            job_id = title_elem["data-jk"]
                        
                        if job_id:
                            job_link = f"https://in.indeed.com/viewjob?jk={job_id}"
                        else:
                            # Try to get link from title element
                            link_elem = title_elem if title_elem and title_elem.name == "a" else job_card.select_one("a")
                            
                            if link_elem and link_elem.has_attr("href"):
                                href = link_elem["href"]
                                if href.startswith("/"):
                                    job_link = f"https://in.indeed.com{href}"
                                else:
                                    job_link = href
                        
                        # Create job
                        if job_title and (job_link or company):
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link or india_url,
                                source="Indeed (India)",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting Indeed job with residential proxy: {str(e)}")
                
                return jobs
            else:
                logging.error(f"Residential proxy method returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with residential proxy method: {str(e)}")
        
        return []
    
    def _scrape_with_alternative_indeed_domains(self, job_request: JobSearchRequest) -> List[Job]:
        """Try scraping from alternative country domains of Indeed"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Try different country domains
        country_domains = ["in", "pk", "ca", "uk", "au"]
        
        for country in country_domains:
            try:
                # Construct URL for this country domain
                url = f"https://{country}.indeed.com/jobs?q={query}&l={location}"
                logging.info(f"Trying Indeed {country} domain: {url}")
                
                # Create a session with specialized headers that look like a real browser
                session = requests.Session()
                
                headers = {
                    "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(90, 114)}.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                    "Cache-Control": "max-age=0",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "cross-site",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "Pragma": "no-cache",
                    "Referer": "https://www.google.com/"
                }
                
                # First visit the homepage to get cookies
                session.get(f"https://{country}.indeed.com/", headers=headers, timeout=10)
                
                # Small delay
                time.sleep(random.uniform(1, 2))
                
                # Now get the job results
                response = session.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # Look for job cards
                    job_cards = (
                        soup.select(".jobsearch-ResultsList .cardOutline") or
                        soup.select(".job_seen_beacon") or
                        soup.select("[data-testid='jobListing']") or
                        soup.select(".resultWithShelf") or
                        soup.select(".tapItem")
                    )
                    
                    if not job_cards:
                        # Try more generic selectors
                        job_cards = soup.select("div[class*='job']") or soup.select("div[id*='job']")
                    
                    logging.info(f"Found {len(job_cards)} job cards from {country}.indeed.com")
                    
                    if not job_cards:
                        continue
                    
                    jobs = []
                    
                    for job_card in job_cards[:10]:
                        try:
                            # Extract job title
                            title_elem = job_card.select_one("h2.jobTitle") or job_card.select_one(".jobTitle") or job_card.select_one("h2")
                            job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                            
                            # Extract company name
                            company_elem = job_card.select_one(".companyName") or job_card.select_one(".company")
                            company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                            
                            # Extract location
                            location_elem = job_card.select_one(".companyLocation") or job_card.select_one(".location")
                            location = self.clean_text(location_elem.get_text()) if location_elem else None
                            
                            # Extract job link
                            link_elem = job_card.select_one("a")
                            job_link = None
                            
                            if link_elem and link_elem.has_attr("href"):
                                href = link_elem["href"]
                                if href.startswith("/"):
                                    job_link = f"https://{country}.indeed.com{href}"
                                else:
                                    job_link = href
                            
                            # Only add the job if we have title and either link or company
                            if job_title and (job_link or company):
                                job = Job(
                                    job_title=job_title,
                                    company=company,
                                    location=location,
                                    experience=None,  # We'll have to live without these details
                                    jobNature=None,
                                    salary=None,
                                    apply_link=job_link or url,
                                    source=f"Indeed ({country})",
                                    description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                    relevance_score=75  # Default relevance score
                                )
                                jobs.append(job)
                        except Exception as e:
                            logging.error(f"Error extracting job from {country}.indeed.com: {str(e)}")
                    
                    if jobs:
                        return jobs
                
                else:
                    logging.error(f"{country}.indeed.com returned status {response.status_code}")
            
            except Exception as e:
                logging.error(f"Error with {country}.indeed.com: {str(e)}")
                continue
        
        return []
    
    def _scrape_with_special_headers(self, job_request: JobSearchRequest) -> List[Job]:
        """Try using specially crafted headers to bypass blocking"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Add cache-busting parameters
        timestamp = int(time.time())
        url = f"https://www.indeed.com/jobs?q={query}&l={location}&sort=date&ts={timestamp}"
        
        logging.info(f"Trying Indeed with special headers: {url}")
        
        try:
            # Create a completely fresh session
            session = requests.Session()
            
            # Use headers that closely mimic a real Chrome browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive",
                "Host": "www.indeed.com",
                "sec-ch-ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Pragma": "no-cache"
            }
            
            # Add common cookies that a browser would have
            session.cookies.set("indeed_rcc", "1", domain=".indeed.com")
            session.cookies.set("JSESSIONID", f"session{random.randint(1000,9999)}", domain=".indeed.com")
            session.cookies.set("INDEED_CSRF_TOKEN", self._generate_random_token(64), domain=".indeed.com")
            session.cookies.set("CTK", self._generate_random_token(20), domain=".indeed.com")
            
            # First visit Google to establish referrer chain
            session.get("https://www.google.com/search?q=indeed+jobs", headers=headers, timeout=10)
            
            # Then visit Indeed homepage
            headers["Referer"] = "https://www.google.com/"
            session.get("https://www.indeed.com/", headers=headers, timeout=10)
            
            # Small delay to look natural
            time.sleep(random.uniform(1.5, 3))
            
            # Now visit the search page
            headers["Referer"] = "https://www.indeed.com/"
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Check for job cards
                job_cards = (
                    soup.select(".jobsearch-ResultsList .cardOutline") or
                    soup.select(".job_seen_beacon") or
                    soup.select("[data-testid='jobListing']") or
                    soup.select(".resultWithShelf") or
                    soup.select(".tapItem")
                )
                
                logging.info(f"Found {len(job_cards)} job cards with special headers")
                
                if not job_cards:
                    return []
                
                jobs = []
                
                # Extract job details
                for job_card in job_cards[:10]:
                    try:
                        # Extract job title
                        title_elem = job_card.select_one("h2.jobTitle") or job_card.select_one(".jobTitle") or job_card.select_one("h2")
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                        
                        # Extract company name
                        company_elem = job_card.select_one(".companyName") or job_card.select_one(".company")
                        company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                        
                        # Extract location
                        location_elem = job_card.select_one(".companyLocation") or job_card.select_one(".location")
                        location = self.clean_text(location_elem.get_text()) if location_elem else None
                        
                        # Extract job link
                        link_elem = job_card.select_one("a")
                        job_link = None
                        
                        if link_elem and link_elem.has_attr("href"):
                            href = link_elem["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.indeed.com{href}"
                            else:
                                job_link = href
                        
                        # Only add the job if we have title and either link or company
                        if job_title and (job_link or company):
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link or url,
                                source="Indeed",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting job with special headers: {str(e)}")
                
                return jobs
            else:
                logging.error(f"Special headers method returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with special headers method: {str(e)}")
        
        return []
    
    def _scrape_with_referer_chains(self, job_request: JobSearchRequest) -> List[Job]:
        """Try using referer chains to appear as if coming from Google"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Format URL with Google query parameters
        google_query = f"site:indeed.com {job_request.position} jobs {job_request.location}"
        direct_url = f"https://www.indeed.com/jobs?q={query}&l={location}"
        
        logging.info(f"Trying Indeed with referer chain: {direct_url}")
        
        try:
            # Create a fresh session
            session = requests.Session()
            
            # Rotating Chrome versions
            chrome_version = random.randint(90, 114)
            
            headers = {
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Step 1: Visit Google search first
            google_url = f"https://www.google.com/search?q={quote(google_query)}"
            session.get(google_url, headers=headers, timeout=10)
            
            # Step 2: Set referer to Google and visit Indeed
            headers["Referer"] = google_url
            response = session.get(direct_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Check for job cards
                job_cards = (
                    soup.select(".jobsearch-ResultsList .cardOutline") or
                    soup.select(".job_seen_beacon") or
                    soup.select("[data-testid='jobListing']") or
                    soup.select(".resultWithShelf") or
                    soup.select(".tapItem")
                )
                
                logging.info(f"Found {len(job_cards)} job cards with referer chain")
                
                if not job_cards:
                    return []
                
                jobs = []
                
                # Extract job details
                for job_card in job_cards[:10]:
                    try:
                        # Extract job title
                        title_elem = job_card.select_one("h2.jobTitle") or job_card.select_one(".jobTitle") or job_card.select_one("h2")
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                        
                        # Extract company name
                        company_elem = job_card.select_one(".companyName") or job_card.select_one(".company")
                        company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                        
                        # Extract location
                        location_elem = job_card.select_one(".companyLocation") or job_card.select_one(".location")
                        location = self.clean_text(location_elem.get_text()) if location_elem else None
                        
                        # Extract job link
                        link_elem = job_card.select_one("a")
                        job_link = None
                        
                        if link_elem and link_elem.has_attr("href"):
                            href = link_elem["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.indeed.com{href}"
                            else:
                                job_link = href
                        
                        # Only add the job if we have title and either link or company
                        if job_title and (job_link or company):
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link or direct_url,
                                source="Indeed",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting job with referer chain: {str(e)}")
                
                return jobs
            else:
                logging.error(f"Referer chain method returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with referer chain method: {str(e)}")
        
        return []
    
    def _scrape_with_country_code_domains(self, job_request: JobSearchRequest) -> List[Job]:
        """Try different country-specific Indeed domains"""
        query = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Try Indeed Pakistan specifically since location is in Pakistan
        country = "pk"  # Pakistan specific domain
        
        url = f"https://{country}.indeed.com/jobs?q={query}&l={location}"
        logging.info(f"Trying Indeed country-specific URL: {url}")
        
        try:
            # Create a session with a mobile user agent to try to bypass blocks
            session = requests.Session()
            
            # Use mobile user agent to potentially access different site version
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us",
                "Connection": "keep-alive",
                "Referer": "https://www.google.com/",
                "Cache-Control": "max-age=0",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # First visit the homepage
            session.get(f"https://{country}.indeed.com/", headers=headers, timeout=10)
            
            # Small delay
            time.sleep(random.uniform(1, 2))
            
            # Make the request
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try to find job listings with various selectors
                job_cards = (
                    soup.select(".jobsearch-ResultsList .cardOutline") or
                    soup.select(".job_seen_beacon") or
                    soup.select("[data-testid='jobListing']") or
                    soup.select(".resultWithShelf") or
                    soup.select(".tapItem") or
                    soup.select("div[class*='job']")  # More generic selector
                )
                
                logging.info(f"Found {len(job_cards)} Indeed job cards from {country} domain")
                
                if not job_cards:
                    return []
                
                jobs = []
                
                # Process job listings
                for job_card in job_cards[:10]:
                    try:
                        # Extract job title
                        title_elem = job_card.select_one("h2.jobTitle") or job_card.select_one(".jobTitle") or job_card.select_one("h2")
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                        
                        # Extract company
                        company_elem = job_card.select_one(".companyName") or job_card.select_one(".company")
                        company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                        
                        # Extract location
                        location_elem = job_card.select_one(".companyLocation") or job_card.select_one(".location")
                        location = self.clean_text(location_elem.get_text()) if location_elem else None
                        
                        # Extract link
                        link_elem = job_card.select_one("a")
                        job_link = None
                        
                        if link_elem and link_elem.has_attr("href"):
                            href = link_elem["href"]
                            if href.startswith("/"):
                                job_link = f"https://{country}.indeed.com{href}"
                            else:
                                job_link = href
                        
                        # Create job
                        if job_title and (job_link or company):
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=location,
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link or url,
                                source=f"Indeed ({country})",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting job from country-specific domain: {str(e)}")
                
                return jobs
            else:
                logging.error(f"Country-specific domain returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with country-specific domain: {str(e)}")
        
        return []
    
    def _generate_random_token(self, length: int) -> str:
        """Generate a random token for fake cookies"""
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return ''.join(random.choice(chars) for _ in range(length))
