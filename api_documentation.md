# Job Finder API Documentation

This documentation provides detailed information about the Job Finder API endpoints, how to use them, and how the job matching functionality works.

## Table of Contents

1. [API Overview](#api-overview)
2. [API Endpoints](#api-endpoints)
   - [Welcome Endpoint](#welcome-endpoint)
   - [Health Check Endpoint](#health-check-endpoint)
   - [Job Sources Endpoint](#job-sources-endpoint)
   - [Job Search Endpoint](#job-search-endpoint)
3. [Job Matching Process](#job-matching-process)
4. [Using the API with Swagger UI](#using-the-api-with-swagger-ui)
5. [Request and Response Examples](#request-and-response-examples)
6. [Error Handling](#error-handling)

## API Overview

The Job Finder API aggregates job listings from multiple popular job platforms (LinkedIn, Indeed, and Glassdoor) and uses advanced AI technology to match jobs with the user's search criteria. The API provides a unified interface for searching across these platforms with intelligent filtering.

![API Architecture]

## API Endpoints

### Welcome Endpoint

**Endpoint:** `GET /`

This endpoint returns a welcome message and basic information about the API.

**Response Example:**
```json
{
  "message": "Welcome to the Job Finder API! Go to /docs for API documentation."
}
```

### Health Check Endpoint

**Endpoint:** `GET /health`

This endpoint provides information about the current state of the API and its components.

**Response Example:**
```json
{
  "status": "OK",
  "time": 1714139870.341,
  "cache_entries": 3,
  "scrapers": ["LinkedIn", "Indeed", "Glassdoor"]
}
```

![Health Check Endpoint]

### Job Sources Endpoint

**Endpoint:** `GET /api/sources`

Provides information about the available job sources that the API can search.

**Response Example:**
```json
{
  "sources": [
    {"name": "LinkedIn", "status": "active"},
    {"name": "Indeed", "status": "active"},
    {"name": "Glassdoor", "status": "active"}
  ]
}
```

![Sources Endpoint]

### Job Search Endpoint

**Endpoint:** `POST /api/search`

This is the main endpoint for searching jobs across multiple platforms.

**Request Parameters:**
| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| position | string | The job title or position | Yes |
| experience | string | Years of experience | No |
| salary | string | Expected salary range | No |
| jobNature | string | Job type (e.g., "Remote", "Full-time") | No |
| location | string | Job location | No |
| skills | string | Required skills | No |

**Request Example:**
```json
{
  "position": "Full Stack Engineer",
  "experience": "2 years",
  "salary": "70,000 PKR to 120,000 PKR",
  "jobNature": "Remote",
  "location": "Karachi, Pakistan",
  "skills": "React, Node.js, MongoDB"
}
```

**Response Example:**
```json
{
  "relevant_jobs": [
    {
      "job_title": "Senior Full Stack Engineer",
      "company": "Tech Solutions Inc.",
      "experience": "2-4 years",
      "jobNature": "Remote",
      "location": "Karachi, Pakistan",
      "salary": "90,000 PKR - 130,000 PKR",
      "apply_link": "https://linkedin.com/jobs/view/123456",
      "source": "LinkedIn",
      "description": "Looking for a skilled Full Stack Engineer with experience in React and Node.js...",
      "relevance_score": 92.5
    },
    // Additional job listings...
  ]
}
```

![Search Endpoint]

## Job Matching Process

The Job Finder API uses a sophisticated matching process to find and rank jobs based on relevance to your search criteria:

### 1. Data Collection Phase

The API simultaneously queries multiple job platforms (LinkedIn, Indeed, and Glassdoor) using advanced scraping techniques that:

- Bypass anti-bot measures
- Handle various HTML structures
- Extract consistent job information from different sources
- Implement retries and fallback mechanisms

![Scraping Process](https://i.imgur.com/L2qRgmD.png)

### 2. AI-Powered Relevance Filtering

Once jobs are collected, they are processed through an LLM (Large Language Model) that:

1. **Analyzes the job content**: The system examines each job's title, description, requirements, and other fields
2. **Compares against search criteria**: Each job is scored based on how well it matches your search parameters
3. **Calculates a relevance score**: Jobs receive a score between 0-100

The relevance scoring prioritizes these factors (in order of importance):
- Job title/position match
- Required skills match
- Experience level match
- Job nature (remote/onsite/hybrid) match
- Location match
- Salary range match (if available)

![AI Filtering Process]

### 3. Keyword Fallback System

If the AI system is unavailable, a robust keyword-based matching system activates that:
- Searches for keyword matches between your search terms and job listings
- Assigns scores based on match frequency and positioning
- Evaluates exact and partial matches
- Uses a weighted scoring algorithm that prioritizes title and skills

### 4. Response Generation

The API returns jobs with:
- A relevance score above 60 (out of 100)
- Sorted from highest to lowest relevance
- Caching to improve performance on repeated searches

## Using the API with Swagger UI

The Job Finder API includes built-in Swagger documentation, accessible at `/docs`. This interactive interface allows you to:

1. Explore all available endpoints
2. Test API calls directly in your browser
3. View request and response schemas
4. Understand parameter requirements


## Request and Response Examples

### Example 1: Remote Developer Position

**Request:**
```json
{
  "position": "React Developer",
  "experience": "1-3 years",
  "jobNature": "Remote",
  "location": "Anywhere",
  "skills": "React, JavaScript, Redux"
}
```

**Response (shortened):**
```json
{
  "relevant_jobs": [
    {
      "job_title": "Remote React Developer",
      "company": "TechStart Inc.",
      "jobNature": "Remote",
      "relevance_score": 95.5,
      // Other job details...
    },
    // More job listings...
  ]
}
```

### Example 2: Local Full-time Position

**Request:**
```json
{
  "position": "Data Analyst",
  "experience": "5+ years",
  "jobNature": "Full-time",
  "location": "Lahore, Pakistan",
  "skills": "SQL, Python, Tableau"
}
```

**Response (shortened):**
```json
{
  "relevant_jobs": [
    {
      "job_title": "Senior Data Analyst",
      "company": "Analytics Co.",
      "location": "Lahore, Pakistan",
      "jobNature": "Full-time",
      "relevance_score": 89.0,
      // Other job details...
    },
    // More job listings...
  ]
}
```

## Error Handling

The API implements robust error handling to ensure a smooth user experience:

### Common Error Scenarios

1. **No Jobs Found**:
   - Returns an empty array: `{"relevant_jobs": []}`
   - Avoids error status codes for cleaner client handling

2. **Invalid Request Parameters**:
   - Returns 422 Unprocessable Entity status code
   - Provides detailed validation error messages

3. **Service Unavailable**:
   - If all job sources fail, returns empty results
   - Background tasks attempt to refresh data

4. **Timeout Handling**:
   - Implements strict timeouts to prevent hanging requests
   - Returns available results even if some sources timeout

### Error Response Example

```json
{
  "detail": [
    {
      "loc": ["body", "position"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

This comprehensive documentation should help you effectively use the Job Finder API to search for relevant job listings across multiple platforms.
