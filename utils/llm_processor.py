import logging
import os
import openai
from typing import List, Dict, Any
from dotenv import load_dotenv
import json

from models.job import Job
from models.request import JobSearchRequest

# Load environment variables
load_dotenv()

class LLMProcessor:
    """
    Process job descriptions using LLM to calculate relevance scores
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logging.warning("OpenAI API key not found. LLM processing will be limited.")
        else:
            openai.api_key = self.api_key
    
    async def filter_jobs_by_relevance(self, jobs: List[Job], job_request: JobSearchRequest) -> List[Job]:
        """
        Filter jobs by relevance to the search criteria
        
        Args:
            jobs: List of job objects to evaluate
            job_request: The original search criteria
            
        Returns:
            List of relevant jobs sorted by relevance score
        """
        if not jobs:
            return []
        
        if not self.api_key:
            logging.warning("No OpenAI API key. Returning all jobs without relevance filtering.")
            return jobs
        
        # Process jobs in batches to avoid API rate limits
        batch_size = 5
        job_batches = [jobs[i:i + batch_size] for i in range(0, len(jobs), batch_size)]
        
        all_processed_jobs = []
        
        for batch in job_batches:
            processed_batch = await self._process_job_batch(batch, job_request)
            all_processed_jobs.extend(processed_batch)
        
        # Sort by relevance score
        relevant_jobs = [job for job in all_processed_jobs if job.relevance_score and job.relevance_score > 60]
        relevant_jobs.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        
        # Only return jobs that the model has determined have a good match
        return relevant_jobs
    
    async def _process_job_batch(self, jobs: List[Job], job_request: JobSearchRequest) -> List[Job]:
        """Process a batch of jobs through the LLM"""
        
        # Create prompt for OpenAI
        system_prompt = """
        You are an expert job recruiter tasked with comparing job listings against a candidate's search criteria.
        Analyze each job listing and calculate a relevance score from 0 to 100 based on how well it matches the search criteria.
        Consider the following factors (in order of importance):
        1. Job title/position match
        2. Required skills match
        3. Experience level match
        4. Job nature (remote/onsite/hybrid) match
        5. Location match
        6. Salary range match (if available)
        
        Return a JSON array of objects, each containing:
        - index: the original index of the job
        - score: the relevance score (0-100)
        - reasons: a short explanation of the score
        """
        
        # Create job descriptions for evaluation
        job_descriptions = []
        for i, job in enumerate(jobs):
            description = (
                f"[JOB {i}]\n"
                f"Title: {job.job_title}\n"
                f"Company: {job.company}\n"
                f"Location: {job.location or 'Not specified'}\n"
                f"Job Nature: {job.jobNature or 'Not specified'}\n"
                f"Experience: {job.experience or 'Not specified'}\n"
                f"Salary: {job.salary or 'Not specified'}\n"
                f"Description: {job.description or 'No description available'}\n"
            )
            job_descriptions.append(description)
        
        # Combine job descriptions
        combined_descriptions = "\n\n".join(job_descriptions)
        
        # Create user prompt with search criteria
        user_prompt = f"""
        SEARCH CRITERIA:
        Position: {job_request.position}
        Skills needed: {job_request.skills}
        Experience required: {job_request.experience}
        Job Nature: {job_request.jobNature}
        Location: {job_request.location}
        Salary range: {job_request.salary}
        
        JOB LISTINGS TO EVALUATE:
        {combined_descriptions}
        
        Analyze each job listing against the search criteria and return relevance scores in JSON format.
        """
        
        try:
            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Extract and parse the response
            response_text = response.choices[0].message.content
            
            # Extract JSON from the response (in case there's text around it)
            try:
                # First try parsing directly
                results = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from the text
                import re
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    results = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not extract JSON from LLM response")
            
            # Update jobs with relevance scores
            for result in results:
                index = result.get("index")
                score = result.get("score")
                
                if index is not None and 0 <= index < len(jobs) and score is not None:
                    jobs[index].relevance_score = float(score)
            
            return jobs
        
        except Exception as e:
            logging.error(f"Error in LLM processing: {str(e)}")
            # If LLM processing fails, return jobs without scores
            return jobs
