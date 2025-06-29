"""
Job Data Model - LinkedIn Job Information Container

This module defines the Job dataclass that encapsulates all information
about a LinkedIn job posting including metadata, description, and application status.

The Job class serves as a standardized data container that is passed between
different components of the application system.

Date: 2025
"""

from dataclasses import dataclass


@dataclass
class Job:
    """
    Data container for LinkedIn job information.
    
    This class encapsulates all relevant information about a job posting
    including basic metadata, job description, and processing status.
    
    Attributes:
        title: Job title/position name
        company: Company name offering the position
        location: Geographic location of the job
        link: Direct URL to the job posting
        apply_method: Method of application (e.g., "Easy Apply", "External")
        description: Full job description text (populated after extraction)
        summarize_job_description: AI-generated summary of job description
    """
    title: str
    company: str
    location: str
    link: str
    apply_method: str
    description: str = ""
    summarize_job_description: str = ""

    def set_summarize_job_description(self, summarize_job_description: str) -> None:
        """
        Set the AI-generated summary of the job description.
        
        Args:
            summarize_job_description: Summarized version of the job description
        """
        self.summarize_job_description = summarize_job_description

    def set_job_description(self, description: str) -> None:
        """
        Set the full job description text.
        
        Args:
            description: Complete job description text extracted from the posting
        """
        self.description = description

    def formatted_job_information(self) -> str:
        """
        Format job information as a structured markdown string.
        
        This method creates a well-formatted representation of the job information
        that can be used for display, logging, or as input to AI systems.
        
        Returns:
            str: Markdown-formatted job information string
        """
        job_information = f"""
        # Job Description
        ## Job Information 
        - Position: {self.title}
        - At: {self.company}
        - Location: {self.location}
        - Apply Method: {self.apply_method}
        - URL: {self.link}
        
        ## Description
        {self.description or 'No description provided.'}
        """
        return job_information.strip()

    def get_unique_identifier(self) -> str:
        """
        Generate a unique identifier for this job posting.
        
        Returns:
            str: Unique identifier based on company, title, and location
        """
        return f"{self.company}_{self.title}_{self.location}".replace(" ", "_").lower()

    def is_easy_apply(self) -> bool:
        """
        Check if this job supports LinkedIn Easy Apply.
        
        Returns:
            bool: True if job supports Easy Apply, False otherwise
        """
        return "easy apply" in self.apply_method.lower()

    def __str__(self) -> str:
        """
        String representation of the job.
        
        Returns:
            str: Human-readable job summary
        """
        return f"{self.title} at {self.company} ({self.location})"
