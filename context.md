# Job Finder API - Implementation Context

## Overview
This project implements a Job Finder API that fetches job listings from multiple online sources (LinkedIn, Indeed, and Glassdoor), processes them using LLM technology, and returns relevant job matches based on user criteria.

## Project Structure
```
job_finder_api/
├── main.py               # FastAPI application entry point
├── requirements.txt      # Project dependencies
├── .env                  # Environment variables (not tracked in git)
├── scrapers/
│   ├── __init__.py
│   ├── linkedin.py       # LinkedIn scraper
│   ├── indeed.py         # Indeed scraper
│   ├── glassdoor.py      # Glassdoor scraper
│   └── base.py           # Base scraper class
├── utils/
│   ├── __init__.py
│   ├── llm_processor.py  # LLM-based relevance filtering
│   └── data_utils.py     # Data formatting utilities
├── models/
│   ├── __init__.py
│   ├── job.py            # Job data models
│   └── request.py        # Request data models
└── tests/
    ├── __init__.py
    └── test_api.py       # API tests
```

## Implementation Details

### 1. Web Scraping Approach
- **LinkedIn**: Using Selenium for dynamic content loading and BeautifulSoup for parsing.
- **Indeed**: Using requests and BeautifulSoup as the content is more accessible.
- **Glassdoor**: Using Selenium to navigate through job listings.

Each scraper inherits from a base scraper class that defines common functionality.

### 2. LLM Relevance Filtering
Using OpenAI's GPT model to:
1. Analyze job descriptions
2. Match them against user-provided criteria
3. Score jobs based on relevance
4. Filter out irrelevant postings

### 3. API Endpoints
- `POST /api/search`: Accepts job search criteria and returns matching jobs
- `GET /api/sources`: Returns the available job sources
- `GET /docs`: API documentation

### 4. Deployment Strategy
The API will be containerized using Docker for easy deployment.

## Next Steps
- Implement rate limiting and caching to avoid hitting job sites too frequently
- Add proxy rotation for more resilient scraping
- Improve error handling and logging
- Add user authentication for production use
- Implement background tasks for periodic job fetching
- Add monitoring for service health
