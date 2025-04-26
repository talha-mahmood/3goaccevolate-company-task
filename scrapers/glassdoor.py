from typing import List
import asyncio
import logging
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlencode
import json
import re

from scrapers.base import BaseScraper
from models.job import Job
from models.request import JobSearchRequest

class GlassdoorScraper(BaseScraper):
    """Glassdoor job scraper implementation with aggressive anti-blocking"""
    
    def __init__(self):
        super().__init__()
        self.name = "Glassdoor"
        self.base_url = "https://www.glassdoor.com/Job/jobs.htm"
        
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Scrape Glassdoor for jobs matching the request criteria
        
        Args:
            job_request: Job search criteria
            
        Returns:
            List of Job objects from Glassdoor
        """
        logging.info(f"Scraping Glassdoor for: {job_request.position}")
        
        # Use a timeout for the thread-based scraping to prevent hanging
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._scrape_glassdoor, job_request),
                timeout=25  # 25 second timeout
            )
        except asyncio.TimeoutError:
            logging.error("Glassdoor scraper timed out after 25 seconds")
            return []
        except Exception as e:
            logging.error(f"Error in Glassdoor scraper: {str(e)}")
            return []
    
    def _scrape_glassdoor(self, job_request: JobSearchRequest) -> List[Job]:
        """Internal method to handle the actual scraping with advanced techniques"""
        
        methods = [
            self._scrape_with_api_emulation,  # Add the new method first
            self._scrape_with_google_referer,
            self._scrape_with_search_url_pattern,
            self._scrape_with_generic_request
        ]
        
        for method in methods:
            try:
                method_name = method.__name__
                logging.info(f"Trying Glassdoor scraping method: {method_name}")
                method_jobs = method(job_request)
                
                if method_jobs:
                    logging.info(f"Successfully found {len(method_jobs)} jobs with {method_name}")
                    return method_jobs
            except Exception as e:
                logging.error(f"Error in {method.__name__}: {str(e)}")
                continue
        
        logging.warning("All Glassdoor scraping methods failed")
        return []
    
    def _scrape_with_google_referer(self, job_request: JobSearchRequest) -> List[Job]:
        """Use Google as a referrer to bypass Glassdoor blocks"""
        position = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Format URL
        url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={position}&locT=C&locId=0&locKeyword={location}"
        
        google_query = f"site:glassdoor.com {job_request.position} jobs {job_request.location}"
        google_url = f"https://www.google.com/search?q={quote(google_query)}"
        
        logging.info(f"Trying Glassdoor with Google referer: {url}")
        
        try:
            # Create a fresh session
            session = requests.Session()
            
            # Use headers that mimic a real browser
            chrome_version = random.randint(90, 114)
            headers = {
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Step 1: Visit Google first
            session.get(google_url, headers=headers, timeout=10)
            
            # Step 2: Use Google as referer to visit Glassdoor
            headers["Referer"] = google_url
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Try to find job listings
                job_cards = (
                    soup.select("li.react-job-listing") or
                    soup.select("div.jobCard") or
                    soup.select("div[data-test='jobListing']") or
                    soup.select("li.jl") or
                    soup.select("div[class*='Job']") or  # Generic fallback
                    soup.select("article")  # Even more generic
                )
                
                logging.info(f"Found {len(job_cards)} Glassdoor job cards with Google referer")
                
                if not job_cards:
                    return []
                
                jobs = []
                
                # Process job listings
                for job_card in job_cards[:10]:
                    try:
                        # Extract job details
                        title_elem = (
                            job_card.select_one("a.jobLink") or 
                            job_card.select_one("a[data-test='job-link']") or
                            job_card.select_one(".job-title") or
                            job_card.select_one("div.jobTitle") or
                            job_card.select_one("h3") or  # Generic fallback
                            job_card.select_one("a")  # Last resort
                        )
                        
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                        
                        # Get company
                        company_elem = (
                            job_card.select_one("[data-test='employerName']") or 
                            job_card.select_one(".jobCompany") or
                            job_card.select_one("div.companyName") or
                            job_card.select_one("div.companyInfo") or
                            job_card.select_one("span.company")  # Generic fallback
                        )
                        
                        company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                        
                        # Get location
                        location_elem = (
                            job_card.select_one("[data-test='location']") or 
                            job_card.select_one(".location") or
                            job_card.select_one("div.companyLocation") or
                            job_card.select_one("span.location")  # Generic fallback
                        )
                        
                        location = self.clean_text(location_elem.get_text()) if location_elem else None
                        
                        # Get job link
                        job_link = None
                        if title_elem and title_elem.has_attr("href"):
                            href = title_elem["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.glassdoor.com{href}"
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
                                source="Glassdoor",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting Glassdoor job with Google referer: {str(e)}")
                
                return jobs
            else:
                logging.error(f"Google referer method returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with Google referer method: {str(e)}")
        
        return []
    
    def _scrape_with_search_url_pattern(self, job_request: JobSearchRequest) -> List[Job]:
        """Try a different URL pattern for Glassdoor search"""
        position_slug = re.sub(r'[^a-zA-Z0-9]', '-', job_request.position.lower()).strip('-')
        location_slug = re.sub(r'[^a-zA-Z0-9]', '-', job_request.location.lower()).strip('-') if job_request.location else "remote"
        
        # Create a slug-based URL (often works when other patterns get blocked)
        url = f"https://www.glassdoor.com/Job/{location_slug}-{position_slug}-jobs-SRCH_IL.0,{len(location_slug)}_IC1122520_KO{len(location_slug)+1},{len(location_slug)+len(position_slug)+1}.htm"
        
        logging.info(f"Trying Glassdoor with slug-based URL: {url}")
        
        try:
            # Create a fresh session
            session = requests.Session()
            
            # Use headers that mimic a real browser
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
            
            # Visit the page
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for job cards
                job_cards = (
                    soup.select("li.react-job-listing") or
                    soup.select("div.jobCard") or
                    soup.select("div[data-test='jobListing']") or
                    soup.select("li.jl") or
                    soup.select("article") or
                    soup.select("div[class*='JobCard']")  # Generic fallback
                )
                
                logging.info(f"Found {len(job_cards)} Glassdoor job cards with slug-based URL")
                
                if not job_cards:
                    return []
                
                jobs = []
                
                # Process job listings
                for job_card in job_cards[:10]:
                    try:
                        # Extract job details
                        title_elem = (
                            job_card.select_one("a.jobLink") or 
                            job_card.select_one("a[data-test='job-link']") or
                            job_card.select_one(".job-title") or
                            job_card.select_one("div.jobTitle") or
                            job_card.select_one("h2") or
                            job_card.select_one("h3") or
                            job_card.select_one("a")  # Last resort
                        )
                        
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                        
                        # Get company
                        company_elem = (
                            job_card.select_one("[data-test='employerName']") or 
                            job_card.select_one(".jobCompany") or
                            job_card.select_one("div.companyName") or
                            job_card.select_one("div.companyInfo") or
                            job_card.select_one("span.company")
                        )
                        
                        company = self.clean_text(company_elem.get_text()) if company_elem else "Unknown Company"
                        
                        # Get location
                        location_elem = (
                            job_card.select_one("[data-test='location']") or 
                            job_card.select_one(".location") or
                            job_card.select_one("div.companyLocation") or
                            job_card.select_one("span.location")
                        )
                        
                        location = self.clean_text(location_elem.get_text()) if location_elem else None
                        
                        # Get job link
                        job_link = None
                        if title_elem and title_elem.has_attr("href"):
                            href = title_elem["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.glassdoor.com{href}"
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
                                source="Glassdoor",
                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting Glassdoor job with slug-based URL: {str(e)}")
                
                return jobs
            else:
                logging.error(f"Slug-based URL method returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with slug-based URL method: {str(e)}")
        
        return []
    
    def _scrape_with_generic_request(self, job_request: JobSearchRequest) -> List[Job]:
        """Last resort method using a generic job search query"""
        # Use a more generic URL format
        position = quote(job_request.position)
        
        # Try without location for broader results
        url = f"https://www.glassdoor.com/Job/jobs.htm?suggestCount=0&suggestChosen=false&clickSource=searchBtn&typedKeyword={position}&sc.keyword={position}&locT=&locId=&jobType="
        
        logging.info(f"Trying Glassdoor with generic request: {url}")
        
        try:
            # Create a fresh session with mobile user agent
            session = requests.Session()
            
            # Use mobile user agent (sometimes bypasses blocks)
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Referer": "https://www.google.com/search?q=glassdoor+jobs",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache"
            }
            
            # Visit the page
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for any job elements with generic selectors
                job_cards = (
                    soup.select("[class*='job']") or
                    soup.select("[class*='Job']") or
                    soup.select("article") or
                    soup.select(".jobTitle") or
                    soup.select("li")  # Very generic fallback
                )
                
                # Filter the job cards to only include those with job titles
                filtered_cards = []
                for card in job_cards:
                    title_elem = card.select_one("a") or card.select_one("h2") or card.select_one("h3")
                    if title_elem and title_elem.get_text().strip():
                        filtered_cards.append(card)
                
                job_cards = filtered_cards[:10]  # Limit to 10
                logging.info(f"Found {len(job_cards)} Glassdoor job cards with generic request")
                
                if not job_cards:
                    return []
                
                jobs = []
                
                # Process job listings
                for job_card in job_cards:
                    try:
                        # Extract job title - find any prominent text that could be a title
                        title_elem = (
                            job_card.select_one("a") or
                            job_card.select_one("h2") or
                            job_card.select_one("h3") or
                            job_card.select_one("span[class*='title']") or
                            job_card.select_one("div[class*='title']")
                        )
                        
                        job_title = self.clean_text(title_elem.get_text()) if title_elem else None
                        
                        # Get job link - any link in the job card
                        job_link = None
                        if title_elem and title_elem.name == "a" and title_elem.has_attr("href"):
                            href = title_elem["href"]
                            if href.startswith("/"):
                                job_link = f"https://www.glassdoor.com{href}"
                            else:
                                job_link = href
                        else:
                            link_elem = job_card.select_one("a")
                            if link_elem and link_elem.has_attr("href"):
                                href = link_elem["href"]
                                if href.startswith("/"):
                                    job_link = f"https://www.glassdoor.com{href}"
                                else:
                                    job_link = href
                        
                        # Try to find company name near the title
                        company = "Unknown Company"
                        if title_elem and title_elem.parent:
                            # Look for siblings or children that might contain company info
                            for elem in title_elem.parent.contents:
                                if elem.name and elem != title_elem:
                                    text = self.clean_text(elem.get_text())
                                    if text and text != job_title and len(text) < 50:
                                        company = text
                                        break
                        
                        # Create job if we have a title
                        if job_title:
                            job = Job(
                                job_title=job_title,
                                company=company,
                                location=job_request.location,  # Use requested location as fallback
                                experience=None,
                                jobNature=None,
                                salary=None,
                                apply_link=job_link or url,
                                source="Glassdoor",
                                description=f"Job listing for {job_title} at {company}",
                                relevance_score=75
                            )
                            jobs.append(job)
                    except Exception as e:
                        logging.error(f"Error extracting Glassdoor job with generic request: {str(e)}")
                
                return jobs
            else:
                logging.error(f"Generic request method returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with generic request method: {str(e)}")
        
        return []
    
    def _scrape_with_api_emulation(self, job_request: JobSearchRequest) -> List[Job]:
        """Emulate the Glassdoor API that their own frontend uses"""
        position = quote(job_request.position)
        location = quote(job_request.location) if job_request.location else ""
        
        # Use the internal API endpoint
        url = f"https://www.glassdoor.com/searchsuggest/typeahead?versionOverride=CURRENT&source=JOBS_DESKTOP&numSuggestions=8&partial={position}"
        logging.info(f"Trying Glassdoor API emulation: {url}")
        
        jobs = []
        
        try:
            # Create a fresh session with browser-like headers
            session = requests.Session()
            
            # Very sophisticated headers mimicking a browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Origin": "https://www.glassdoor.com",
                "Referer": "https://www.glassdoor.com/",
                "X-Requested-With": "XMLHttpRequest",
                "X-API-Key": f"{self._generate_random_token(32)}",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin"
            }
            
            # Add custom cookies that mimic a real session
            cookies = {
                "trscd": f"{random.randint(1000000, 9999999)}",
                "gdId": f"{self._generate_random_token(20)}",
                "gdsid": f"{self._generate_random_token(32)}",
                "JSESSIONID": f"{self._generate_random_token(32)}",
                "G_ENABLED_IDPS": "google",
                "G_AUTHUSER_H": "0"
            }
            
            for name, value in cookies.items():
                session.cookies.set(name, value, domain=".glassdoor.com")
            
            # First visit the homepage to get cookies
            session.get("https://www.glassdoor.com/", headers=headers, timeout=10)
            
            # Short delay
            time.sleep(random.uniform(1.5, 3))
            
            # Then request the API endpoint
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    # Parse the JSON response
                    data = response.json()
                    suggestions = data.get("suggestions", [])
                    
                    if suggestions:
                        logging.info(f"Found {len(suggestions)} job suggestions from Glassdoor API")
                        
                        for suggestion in suggestions[:10]:
                            job_type = suggestion.get("type")
                            if job_type == "JOBS":
                                try:
                                    job_title = suggestion.get("label", "Unknown Position")
                                    company = suggestion.get("employerName", "Unknown Company")
                                    location = suggestion.get("location", job_request.location)
                                    
                                    # Get the job URL
                                    job_link = suggestion.get("link")
                                    if job_link and not job_link.startswith(("http://", "https://")):
                                        job_link = f"https://www.glassdoor.com{job_link}"
                                    
                                    # Create job
                                    if job_title and (job_link or company):
                                        job = Job(
                                            job_title=job_title,
                                            company=company,
                                            location=location,
                                            experience=None,
                                            jobNature=None,
                                            salary=None,
                                            apply_link=job_link or f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={position}",
                                            source="Glassdoor",
                                            description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                            relevance_score=75
                                        )
                                        jobs.append(job)
                                except Exception as e:
                                    logging.error(f"Error processing Glassdoor suggestion: {str(e)}")
                    
                    # If we couldn't get suggestions, try a different approach
                    if not jobs:
                        # Use search API format
                        search_url = f"https://www.glassdoor.com/graph/api"
                        search_headers = headers.copy()
                        search_headers.update({
                            "Content-Type": "application/json",
                        })
                        
                        # GraphQL query
                        payload = {
                            "operationName": "JobSearch",
                            "variables": {
                                "keyword": job_request.position,
                                "location": job_request.location,
                                "pageNumber": 1,
                                "limit": 10
                            },
                            "query": "query JobSearch($keyword: String!, $location: String, $pageNumber: Int, $limit: Int) { jobSearch(keyword: $keyword, location: $location, pageNumber: $pageNumber, limit: $limit) { jobListings { job { title company { name } location } } } }"
                        }
                        
                        search_response = session.post(search_url, json=payload, headers=search_headers, timeout=15)
                        
                        if search_response.status_code == 200:
                            try:
                                search_data = search_response.json()
                                job_listings = search_data.get("data", {}).get("jobSearch", {}).get("jobListings", [])
                                
                                if job_listings:
                                    logging.info(f"Found {len(job_listings)} jobs from Glassdoor GraphQL API")
                                    
                                    for job_listing in job_listings[:10]:
                                        job_data = job_listing.get("job", {})
                                        job_title = job_data.get("title")
                                        company = job_data.get("company", {}).get("name", "Unknown Company")
                                        location = job_data.get("location")
                                        
                                        if job_title and company:
                                            job = Job(
                                                job_title=job_title,
                                                company=company,
                                                location=location,
                                                experience=None,
                                                jobNature=None,
                                                salary=None,
                                                apply_link=f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={position}",
                                                source="Glassdoor",
                                                description=f"Job listing for {job_title} at {company}" + (f" in {location}" if location else ""),
                                                relevance_score=75
                                            )
                                            jobs.append(job)
                            except Exception as e:
                                logging.error(f"Error processing Glassdoor GraphQL API: {str(e)}")
                except json.JSONDecodeError:
                    logging.error("Failed to parse Glassdoor API JSON response")
            else:
                logging.error(f"Glassdoor API emulation returned status {response.status_code}")
        
        except Exception as e:
            logging.error(f"Error with Glassdoor API emulation: {str(e)}")
        
        return jobs

    def _generate_random_token(self, length: int) -> str:
        """Generate a random token for fake cookies"""
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return ''.join(random.choice(chars) for _ in range(length))
