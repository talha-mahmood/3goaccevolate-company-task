# Job Finder API

A FastAPI-based API that fetches relevant job listings from LinkedIn, Indeed, and Glassdoor based on user-provided search criteria.

## Features

- Fetches job listings from multiple sources:
  - LinkedIn
  - Indeed
  - Glassdoor
- Filters jobs for relevance using OpenAI's GPT model
- Returns structured job data in a consistent format
- Supports detailed search criteria including position, experience, salary, job nature, and skills

## Installation

### Prerequisites

- Python 3.8+
- Chrome browser (for web scraping)
- OpenAI API key

### Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd job-finder-api
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file from the example:
   ```
   cp .env.example .env
   ```

5. Add your OpenAI API key to the `.env` file:
   ```
   OPENAI_API_KEY=your_key_here
   ```

## Usage

### Starting the Server

Run the following command:

```
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

### API Documentation

Once the server is running, visit http://localhost:8000/docs for interactive API documentation.

### Example Request

```bash
curl -X 'POST' \
  'http://localhost:8000/api/search' \
  -H 'Content-Type: application/json' \
  -d '{
  "position": "Full Stack Engineer",
  "experience": "2 years",
  "salary": "70,000 PKR to 120,000 PKR",
  "jobNature": "onsite",
  "location": "Peshawar, Pakistan",
  "skills": "full stack, MERN, Node.js, Express.js, React.js, Next.js, Firebase, TailwindCSS, CSS Frameworks, Tokens handling"
}'
```

### Example Response

```json
{
  "relevant_jobs": [
    {
      "job_title": "Full Stack Engineer",
      "company": "XYZ Pvt Ltd",
      "experience": "2+ years",
      "jobNature": "onsite",
      "location": "Islamabad, Pakistan",
      "salary": "100,000 PKR",
      "apply_link": "https://linkedin.com/job123",
      "source": "LinkedIn"
    },
    {
      "job_title": "MERN Stack Developer",
      "company": "ABC Technologies",
      "experience": "2 years",
      "jobNature": "onsite",
      "location": "Lahore, Pakistan",
      "salary": "90,000 PKR",
      "apply_link": "https://indeed.com/job456",
      "source": "Indeed"
    }
  ]
}
```

## Docker Deployment

You can also run the application using Docker:

```
docker build -t job-finder-api .
docker run -p 8000:8000 --env-file .env job-finder-api
```

## Notes

- Job scraping may take a few seconds to complete as it needs to fetch data from multiple sources.
- Some job sites may have anti-scraping measures that could occasionally affect results.
- The OpenAI API incurs costs based on usage. Monitor your usage to avoid unexpected charges.
