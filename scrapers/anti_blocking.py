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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.50",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 OPR/100.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
]

# Free proxies list - you can replace with your own paid proxies for better reliability
FREE_PROXIES = [
    # Format: {"http": "http://user:pass@host:port", "https": "http://user:pass@host:port"}
    # Free proxies often don't work well, so include None as an option to use direct connection
    None,
    {"http": "http://185.162.231.166:80"},
    {"http": "http://51.79.52.80:3128"},
    {"http": "http://178.62.68.9:80"},
    {"http": "http://185.199.229.156:7492"},
    {"http": "http://185.199.228.220:7300"}
]

class AntiBlockingSession:
    """Session manager with anti-blocking techniques but optimized for performance"""
    
    def __init__(self, site_name: str):
        self.site_name = site_name
        self.session = self._create_session()
        self.cookies: RequestsCookieJar = self.session.cookies
        self.headers = self._get_default_headers()
        self.proxy = self._get_random_proxy()
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests
        
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
            session.timeout = 20
            return session
        except Exception as e:
            logging.error(f"Error creating CloudScraper session: {e}. Using standard requests.")
            session = requests.Session()
            session.timeout = 20
            return session
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get randomized default headers"""
        user_agent = self._get_random_user_agent()
        chrome_version = random.randint(90, 114)
        
        return {
            "User-Agent": user_agent,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "sec-ch-ua": f'"Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}", "Not=A?Brand";v="{random.randint(8, 24)}"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": random.choice(['"Windows"', '"macOS"']),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": random.choice(["none", "same-origin"]),
            "Sec-Fetch-User": "?1",
            "Referer": random.choice([
                "https://www.google.com/",
                "https://www.bing.com/",
                "https://duckduckgo.com/"
            ]),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1"  # Do Not Track
        }
    
    def _get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        global ua
        try:
            # Lazy load fake_useragent to avoid startup delay
            if 'ua' not in globals() or ua is None:
                from fake_useragent import UserAgent
                ua = UserAgent()
            return ua.random
        except Exception:
            return random.choice(FALLBACK_USER_AGENTS)
    
    def _get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random proxy from the pool"""
        return random.choice(FREE_PROXIES)
    
    def _rotate_proxy(self) -> None:
        """Rotate to a different proxy if current one isn't working"""
        current_proxy = self.proxy
        while self.proxy == current_proxy:
            self.proxy = self._get_random_proxy()
        logging.info(f"Rotated proxy for {self.site_name}")
    
    def _refresh_session(self) -> None:
        """Create a fresh session with new cookies and headers"""
        self.session = self._create_session()
        self.cookies = self.session.cookies
        self.headers = self._get_default_headers()
        logging.info(f"Refreshed session for {self.site_name}")
    
    @retry(
        stop=stop_after_attempt(3),  # Retry twice (3 attempts total)
        wait=wait_fixed(2),  # Wait 2 seconds between retries
        retry=retry_if_exception_type((RequestException, Timeout))
    )
    def get(self, url: str, params: Dict[str, Any] = None, timeout: int = 20, **kwargs) -> Any:
        """Make a GET request with optimized timing and automatic retry logic"""
        # Respect rate limiting - ensure minimum time between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last + random.uniform(0, 1)
            time.sleep(sleep_time)
        
        # Use our default headers if none provided
        if 'headers' not in kwargs:
            headers = self.headers
        else:
            # Merge with our default headers rather than replacing
            headers = self.headers.copy()
            headers.update(kwargs.pop('headers'))
        
        # If kwargs doesn't contain proxies, add our proxy
        if 'proxies' not in kwargs and self.proxy:
            kwargs['proxies'] = self.proxy
        
        try:
            response = self.session.get(
                url, 
                params=params,
                headers=headers,
                timeout=timeout,
                **kwargs
            )
            
            # Log response status
            logging.info(f"Request to {url}: Status {response.status_code}")
            
            # Handle potential blocks
            if response.status_code in [403, 429, 503]:
                logging.warning(f"Possible blocking from {self.site_name} (status {response.status_code})")
                
                # Try to rotate proxy and refresh session
                self._rotate_proxy()
                self._refresh_session()
                
                # Retry with the new setup - use headers directly to avoid duplicate
                response = self.session.get(
                    url, 
                    params=params,
                    headers=headers,
                    proxies=self.proxy,
                    timeout=timeout,
                    **{k: v for k, v in kwargs.items() if k != 'headers' and k != 'proxies'}
                )
            
            self.last_request_time = time.time()
            return response
            
        except Timeout:
            logging.error(f"Timeout requesting {url}")
            self.last_request_time = time.time()
            raise
        except Exception as e:
            logging.error(f"Error making request to {url}: {str(e)}")
            self.last_request_time = time.time()
            raise

# Dictionary to store and reuse sessions for different sites
_sessions = {}

def get_session(site_name: str) -> AntiBlockingSession:
    """Get or create an AntiBlockingSession for a specific site"""
    if site_name not in _sessions:
        _sessions[site_name] = AntiBlockingSession(site_name)
    return _sessions[site_name]

def clear_session(site_name: str) -> None:
    """Clear a stored session to force creation of a new one"""
    if site_name in _sessions:
        del _sessions[site_name]
        logging.info(f"Cleared session for {site_name}")
