from typing import Dict, Any, List
import re

def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and newlines
    
    Args:
        text: The text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_salary_range(text: str) -> str:
    """
    Extract salary information from text
    
    Args:
        text: Text containing salary information
        
    Returns:
        Extracted salary range or None
    """
    if not text:
        return None
    
    # Look for common salary patterns
    # Example: $50,000 - $70,000
    salary_match = re.search(r'(\$[\d,]+\s*-\s*\$[\d,]+)', text)
    if salary_match:
        return salary_match.group(1)
    
    # Example: 50K - 70K
    salary_match = re.search(r'([\d,]+K\s*-\s*[\d,]+K)', text, re.IGNORECASE)
    if salary_match:
        return salary_match.group(1)
    
    # Example: PKR 50,000 - PKR 70,000
    salary_match = re.search(r'(PKR\s*[\d,]+\s*-\s*PKR\s*[\d,]+)', text, re.IGNORECASE)
    if salary_match:
        return salary_match.group(1)
    
    return None

def extract_experience_requirement(text: str) -> str:
    """
    Extract experience requirement from text
    
    Args:
        text: Text containing experience information
        
    Returns:
        Extracted experience or None
    """
    if not text:
        return None
    
    # Look for common experience patterns
    # Example: 2+ years of experience
    exp_match = re.search(r'(\d+\+?\s*(?:years|yrs)(?:\s*of)?\s*experience)', text, re.IGNORECASE)
    if exp_match:
        return exp_match.group(1)
    
    # Example: 2-4 years experience
    exp_match = re.search(r'(\d+\s*-\s*\d+\s*(?:years|yrs)(?:\s*of)?\s*experience)', text, re.IGNORECASE)
    if exp_match:
        return exp_match.group(1)
    
    return None

def extract_job_nature(text: str) -> str:
    """
    Extract job nature from text (remote, onsite, hybrid)
    
    Args:
        text: Text containing job nature information
        
    Returns:
        Extracted job nature or None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    if "remote" in text_lower:
        return "remote"
    elif "onsite" in text_lower or "on-site" in text_lower or "on site" in text_lower:
        return "onsite"
    elif "hybrid" in text_lower:
        return "hybrid"
    
    return None
