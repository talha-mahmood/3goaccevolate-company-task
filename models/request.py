from pydantic import BaseModel, Field

class JobSearchRequest(BaseModel):
    position: str = Field(..., description="Job title or position")
    experience: str = Field(..., description="Required experience (e.g., '2 years')")
    salary: str = Field(..., description="Expected salary range (e.g., '70,000 PKR to 120,000 PKR')")
    jobNature: str = Field(..., description="Nature of job (onsite, remote, hybrid)")
    location: str = Field(..., description="Job location (e.g., 'Peshawar, Pakistan')")
    skills: str = Field(..., description="Required skills, comma separated")
    
    class Config:
        schema_extra = {
            "example": {
                "position": "Full Stack Engineer",
                "experience": "2 years",
                "salary": "70,000 PKR to 120,000 PKR",
                "jobNature": "onsite",
                "location": "Peshawar, Pakistan",
                "skills": "full stack, MERN, Node.js, Express.js, React.js, Next.js, Firebase, TailwindCSS, CSS Frameworks, Tokens handling"
            }
        }
