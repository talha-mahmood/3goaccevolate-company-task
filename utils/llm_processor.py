import logging
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import json
import re

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
        
        # Import OpenAI in a compatible way
        try:
            # Try importing the new OpenAI client (v1.0.0+)
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            self.use_new_client = True
            logging.info("Using new OpenAI client (v1.0.0+)")
        except (ImportError, Exception):
            # Fall back to the legacy OpenAI API
            try:
                import openai as legacy_openai
                legacy_openai.api_key = self.api_key
                self.legacy_openai = legacy_openai
                self.use_new_client = False
                logging.info("Using legacy OpenAI client (<v1.0.0)")
            except ImportError:
                logging.error("Failed to import OpenAI module")
                self.use_new_client = None  # Neither version available
    
    async def filter_jobs_without_llm(self, jobs: List[Job], job_request: JobSearchRequest) -> List[Job]:
        """
        Simple keyword-based filtering when LLM is unavailable
        """
        logging.info("Using fallback keyword-based filtering (LLM unavailable)")
        
        # Extract keywords from job request
        position_words = job_request.position.lower().split()
        
        # Score jobs based on keyword matches
        scored_jobs = []
        for job in jobs:
            score = 50  # Base score
            
            # Check position match
            position_match = 0
            if job.job_title:
                title_lower = job.job_title.lower()
                for word in position_words:
                    if word in title_lower:
                        position_match += 1
                
                # Add score based on title match percentage
                if position_words:
                    title_match_percentage = position_match / len(position_words)
                    score += title_match_percentage * 30
            
            # Check location match
            if job_request.location and job.location:
                if job_request.location.lower() in job.location.lower():
                    score += 10
            
            # Add to scored jobs
            job.relevance_score = min(round(score), 100)  # Cap at 100
            scored_jobs.append(job)
        
        # Sort by relevance score
        sorted_jobs = sorted(scored_jobs, key=lambda x: x.relevance_score, reverse=True)
        
        return sorted_jobs

    async def filter_jobs_by_relevance(self, jobs: List[Job], job_request: JobSearchRequest) -> List[Job]:
        """
        Filter jobs by relevance using OpenAI LLM
        
        Args:
            jobs: List of jobs to filter
            job_request: Original job search request
            
        Returns:
            List of jobs filtered and sorted by relevance
        """
        if not jobs:
            return []
        
        # Check if we should use OpenAI
        try:
            if not self.api_key:
                logging.warning("OpenAI API key not available, using fallback filtering")
                return await self.filter_jobs_without_llm(jobs, job_request)
            
            # Try the OpenAI approach first
            try:
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
            
            except Exception as e:
                logging.error(f"Error in LLM processing: {str(e)}")
                logging.info("Falling back to keyword-based filtering")
                return await self.filter_jobs_without_llm(jobs, job_request)
            
        except Exception as e:
            logging.error(f"Error in LLM processing: {str(e)}")
            logging.info("Falling back to keyword-based filtering")
            return await self.filter_jobs_without_llm(jobs, job_request)
    
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
            # Call OpenAI API using the appropriate client version
            if self.use_new_client is True:
                # New OpenAI client (v1.0.0+)
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                response_text = response.choices[0].message.content
            elif self.use_new_client is False:
                # Legacy OpenAI client (<v1.0.0)
                response = await self.legacy_openai.ChatCompletion.acreate(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                response_text = response.choices[0].message.content
            else:
                # No OpenAI client available
                logging.error("No OpenAI client available")
                return jobs
            
            # Extract JSON from the response (in case there's text around it)
            try:
                # First try parsing directly
                results = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from the text
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
