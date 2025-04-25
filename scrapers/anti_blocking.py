"""
Anti-blocking utilities for web scraping
"""
import random
import time
import logging
from typing import Dict, Any, Optional, List
import cloudscraper
from requests.cookies import RequestsCookieJar
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import requests
from requests.exceptions import RequestException, Timeout

# Minimal number of user agents to avoid excessive initialization time
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
]

# Initialize fake user agent generator lazily to avoid startup delay
ua = None
try:
    from fake_useragent import UserAgent
    ua = UserAgent()
except Exception as e:
    logging.warning(f"Could not initialize fake_useragent: {e}. Using fallback user agents.")

class AntiBlockingSession:
    """Session manager with anti-blocking techniques but optimized for performance"""
    
    def __init__(self, site_name: str):
        self.site_name = site_name
        self.session = self._create_session()
        self.cookies: RequestsCookieJar = self.session.cookies
        self.headers = self._get_default_headers()
        
        logging.info(f"Initialized anti-blocking session for {site_name}")
    
    def _create_session(self) -> Any:
        """Create a session with CloudScraper to bypass anti-bot measures"""
        try:
            # Create a basic cloudscraper session with minimal options
            session = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                },
                delay=1  # Use minimal delay
            )
            # Set a reasonable timeout
            session.timeout = 10
            return session
        except Exception as e:
            logging.error(f"Error creating CloudScraper session: {e}. Using standard requests.")
            session = requests.Session()
            session.timeout = 10
            return session
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get randomized default headers"""
        user_agent = self._get_random_user_agent()
        
        return {
            "User-Agent": user_agent,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
            "Referer": random.choice([
                "https://www.google.com/",
                "https://www.bing.com/"
            ]),
        }
    
    def _get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        global ua
        try:
            if ua:
                return ua.random
            else:
                return random.choice(FALLBACK_USER_AGENTS)
        except Exception:
            return random.choice(FALLBACK_USER_AGENTS)
    
    @retry(
        stop=stop_after_attempt(2),  # Only retry once
        wait=wait_fixed(1),  # Wait 1 second between retries
        retry=retry_if_exception_type(RequestException)
    )
    def get(self, url: str, params: Dict[str, Any] = None, timeout: int = 10) -> Any:
        """Make a GET request with optimized timing"""
        # Minimal delay (0-1 second) to avoid excessive waiting
        time.sleep(random.uniform(0, 1))
        
        try:
            response = self.session.get(
                url, 
                headers=self.headers,
                params=params,
                timeout=timeout  # Lower timeout to prevent hanging
            )
            
            # Log response status
            logging.info(f"Request to {url}: Status {response.status_code}")
            
            return response
            
        except Timeout:
            logging.error(f"Timeout requesting {url}")
            raise
        except Exception as e:
            logging.error(f"Error making request to {url}: {str(e)}")
            raise

# Dictionary to store and reuse sessions for different sites
_sessions = {}

def get_session(site_name: str) -> AntiBlockingSession:
    """Get or create an AntiBlockingSession for a specific site"""
    if site_name not in _sessions:
        _sessions[site_name] = AntiBlockingSession(site_name)
    return _sessions[site_name]
