from typing import List
import asyncio
import logging
import random
from pydantic import HttpUrl

from scrapers.base import BaseScraper
from models.job import Job
from models.request import JobSearchRequest

class MockScraper(BaseScraper):
    """Mock job scraper implementation for testing"""
    
    def __init__(self, source_name="Mock"):
        super().__init__()
        self.name = source_name
    
    async def scrape(self, job_request: JobSearchRequest) -> List[Job]:
        """
        Generate mock job listings based on the request criteria
        
        Args:
            job_request: Job search criteria
            
        Returns:
            List of mock Job objects
        """
        logging.info(f"Generating mock jobs for {self.name} source: {job_request.position}")
        
        # Create a list of mock jobs
        jobs = []
        
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # Generate company names
        companies = [
            "TechSolutions Inc.",
            "DigitalCraft Labs",
            "WebFusion Technologies",
            "ByteWorks Software",
            "CodeNest Systems",
            "InnovateTech",
            "DevHarbor",
            "PixelPulse Media",
            "SynthLogic",
            "AppMasters"
        ]
        
        # Generate locations (prefer using the requested location)
        locations = [
            job_request.location,
            "Islamabad, Pakistan",
            "Karachi, Pakistan",
            "Lahore, Pakistan", 
            "Peshawar, Pakistan",
            "Faisalabad, Pakistan"
        ]
        
        # Generate job natures
        job_natures = ["Remote", "Onsite", "Hybrid"]
        
        # Generate experience requirements
        experiences = ["1-2 years", "2+ years", "2-3 years", "Entry level", "Mid-level"]
        
        # Generate salary ranges
        salaries = [
            "60,000 - 90,000 PKR",
            "70,000 - 100,000 PKR",
            "80,000 - 120,000 PKR",
            "90,000 - 130,000 PKR",
            "100,000 - 150,000 PKR"
        ]
        
        # Parse the requested skills
        requested_skills = [skill.strip() for skill in job_request.skills.split(",")]
        
        # Generate job titles related to the requested position
        position_tokens = job_request.position.lower().split()
        
        # Related job titles
        related_titles = [
            job_request.position,
            f"Senior {job_request.position}",
            f"{job_request.position} Developer"
        ]
        
        if "full stack" in job_request.position.lower():
            related_titles.extend([
                "MERN Stack Developer",
                "Full Stack JavaScript Developer",
                "Full Stack Web Developer",
                "React Developer",
                "Node.js Developer"
            ])
        elif "frontend" in job_request.position.lower() or "front end" in job_request.position.lower():
            related_titles.extend([
                "Frontend Developer",
                "React Developer",
                "UI Developer",
                "JavaScript Developer"
            ])
        elif "backend" in job_request.position.lower() or "back end" in job_request.position.lower():
            related_titles.extend([
                "Backend Developer",
                "Node.js Developer",
                "API Developer",
                "Server-side Developer"
            ])
        
        # Generate descriptions with skills from the request
        for i in range(10):  # Generate 10 mock jobs
            # Choose a job title
            job_title = random.choice(related_titles)
            
            # Choose a subset of skills (emphasizing the requested ones)
            skills_subset = random.sample(requested_skills, min(len(requested_skills), random.randint(3, len(requested_skills))))
            
            # Add some common skills
            common_skills = ["JavaScript", "HTML", "CSS", "Git", "RESTful APIs", "Software Development"]
            skills_subset.extend(random.sample(common_skills, random.randint(1, 3)))
            
            # Create a description that incorporates the skills
            skills_text = ", ".join(skills_subset)
            description = f"""
            We are looking for a {job_title} to join our team.
            
            Required Skills:
            {skills_text}
            
            Experience: {random.choice(experiences)}
            
            Job Description:
            As a {job_title}, you will be responsible for developing and maintaining web applications.
            You will work with a team of developers to create high-quality, scalable software solutions.
            
            Responsibilities:
            - Develop and maintain web applications
            - Collaborate with cross-functional teams
            - Write clean, maintainable code
            - Troubleshoot and debug applications
            - Implement security and data protection measures
            
            Requirements:
            - {random.choice(experiences)} experience in {job_request.position}
            - Proficiency in {", ".join(random.sample(skills_subset, min(len(skills_subset), 3)))}
            - Strong problem-solving skills
            - Good communication skills
            """
            
            # Choose job attributes with higher probability of matching request
            nature = job_request.jobNature if random.random() < 0.7 else random.choice(job_natures)
            location = job_request.location if random.random() < 0.7 else random.choice(locations)
            
            # Create the mock job
            job = Job(
                job_title=job_title,
                company=random.choice(companies),
                location=location,
                experience=random.choice(experiences),
                jobNature=nature,
                salary=random.choice(salaries),
                apply_link=f"https://example.com/jobs/{i}",
                source=self.name,
                description=description,
                relevance_score=None  # Let the LLM determine relevance
            )
            
            jobs.append(job)
        
        return jobs
