"""
Resume Data Model - Resume Information Processing and Management

This module defines data classes and processing logic for handling resume information.
It provides structured data containers for different sections of a resume including:
- Personal information and contact details
- Work experience and employment history
- Education and qualifications
- Skills and competencies
- Legal authorization and work preferences

The Resume class serves as the main interface for loading, parsing, and accessing
resume data from YAML files or plain text sources.

Date: 2025
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import yaml


@dataclass
class PersonalInformation:
    """
    Container for personal contact information and details.
    
    Attributes:
        name: First name
        surname: Last name
        dateOfBirth: Date of birth in YYYY-MM-DD format
        country: Country of residence
        city: City of residence
        address: Full street address
        phone: Phone number
        phonePrefix: International phone prefix
        email: Email address
        github: GitHub profile URL
        linkedin: LinkedIn profile URL
    """
    name: str
    surname: str
    dateOfBirth: str
    country: str
    city: str
    address: str
    phone: str
    phonePrefix: str
    email: str
    github: str
    linkedin: str


@dataclass
class SelfIdentification:
    """
    Container for self-identification information.
    
    Used for diversity and inclusion reporting, typically optional
    fields in job applications.
    
    Attributes:
        gender: Gender identification
        pronouns: Preferred pronouns
        veteran: Veteran status
        disability: Disability status
        ethnicity: Ethnic background
    """
    gender: str
    pronouns: str
    veteran: str
    disability: str
    ethnicity: str


@dataclass
class LegalAuthorization:
    """
    Container for work authorization and visa status information.
    
    Tracks legal authorization to work in different regions and
    visa/sponsorship requirements.
    
    Attributes:
        euWorkAuthorization: EU work authorization status
        usWorkAuthorization: US work authorization status
        requiresUsVisa: Whether US visa is required
        legallyAllowedToWorkInUs: Legal permission to work in US
        requiresUsSponsorship: Whether US sponsorship is needed
        requiresEuVisa: Whether EU visa is required
        legallyAllowedToWorkInEu: Legal permission to work in EU
        requiresEuSponsorship: Whether EU sponsorship is needed
    """
    euWorkAuthorization: str
    usWorkAuthorization: str
    requiresUsVisa: str
    legallyAllowedToWorkInUs: str
    requiresUsSponsorship: str
    requiresEuVisa: str
    legallyAllowedToWorkInEu: str
    requiresEuSponsorship: str


@dataclass
class WorkPreferences:
    """
    Container for work preferences and conditions.
    
    Attributes:
        remoteWork: Preference for remote work arrangements
        inPersonWork: Preference for in-person work
        openToRelocation: Willingness to relocate for work
        willingToCompleteAssessments: Willingness to complete skill assessments
        willingToUndergoDrugTests: Willingness to undergo drug testing
        willingToUndergoBackgroundChecks: Willingness for background checks
    """
    remoteWork: str
    inPersonWork: str
    openToRelocation: str
    willingToCompleteAssessments: str
    willingToUndergoDrugTests: str
    willingToUndergoBackgroundChecks: str


@dataclass
class Education:
    """
    Container for educational background information.
    
    Attributes:
        degree: Degree title and level
        university: Institution name
    """
    degree: str
    university: str
    gpa: str
    graduationYear: str
    fieldOfStudy: str
    skillsAcquired: Dict[str, str]


@dataclass
class Experience:
    """
    Container for work experience information.
    
    Attributes:
        position: Job title or position name
        company: Company or organization name
        employmentPeriod: Duration of employment (e.g., "2020-2023")
        location: Work location (city, state/country)
        industry: Industry sector
        keyResponsibilities: Dictionary of key responsibilities and achievements
        skillsAcquired: Dictionary of skills gained during this role
    """
    position: str
    company: str
    employmentPeriod: str
    location: str
    industry: str
    keyResponsibilities: Dict[str, str]
    skillsAcquired: Dict[str, str]


@dataclass
class Availability:
    """
    Container for job availability information.
    
    Attributes:
        noticePeriod: Required notice period for current employment
    """
    noticePeriod: str


@dataclass
class SalaryExpectations:
    """
    Container for salary expectation information.
    
    Attributes:
        salaryRangeUSD: Expected salary range in USD
    """
    salaryRangeUSD: str


@dataclass
class Language:
    """
    Container for language proficiency information.
    
    Attributes:
        language: Language name
        proficiency: Proficiency level (e.g., "Native", "Fluent", "Intermediate")
    """
    language: str
    proficiency: str


class Resume:
    """
    Main resume class that processes and contains all resume information.
    
    This class loads resume data from YAML format and provides structured
    access to all resume sections including personal information, experience,
    education, skills, and preferences.
    """
    
    def __init__(self, yaml_str: str):
        """
        Initialize resume from YAML string content.
        
        Args:
            yaml_str: YAML-formatted string containing resume data
            
        Raises:
            yaml.YAMLError: If YAML content is malformed
            KeyError: If required resume sections are missing
        """
        try:
            data = yaml.safe_load(yaml_str)
            
            # Load all resume sections
            self.personal_information = PersonalInformation(**data['personal_information'])
            self.self_identification = SelfIdentification(**data['self_identification'])
            self.legal_authorization = LegalAuthorization(**data['legal_authorization'])
            self.work_preferences = WorkPreferences(**data['work_preferences'])
            self.education_details = [Education(**edu) for edu in data['education_details']]
            self.experience_details = [Experience(**exp) for exp in data['experience_details']]
            self.projects = data['projects']
            self.availability = Availability(**data['availability'])
            self.salary_expectations = SalaryExpectations(**data['salary_expectations'])
            self.certifications = data['certifications']
            self.languages = [Language(**lang) for lang in data['languages']]
            self.interests = data['interests']
            
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse resume YAML: {e}")
        except KeyError as e:
            raise KeyError(f"Missing required resume section: {e}")

    def get_personal_info(self) -> Dict[str, str]:
        """
        Get personal information as a dictionary.
        
        Returns:
            Dict[str, str]: Personal information with standardized keys
        """
        return {
            'first_name': self.personal_information.name,
            'last_name': self.personal_information.surname,
            'email': self.personal_information.email,
            'phone': f"{self.personal_information.phonePrefix}{self.personal_information.phone}",
            'location': f"{self.personal_information.city}, {self.personal_information.country}",
            'linkedin': self.personal_information.linkedin,
            'github': self.personal_information.github
        }

    def get_years_of_experience(self) -> int:
        """
        Calculate total years of work experience.
        
        Returns:
            int: Total years of professional experience
        """
        # Simple calculation - count number of experience entries
        # In a real implementation, you'd parse employment periods
        return len(self.experience_details)

    def get_skills_summary(self) -> List[str]:
        """
        Get a comprehensive list of all skills from education and experience.
        
        Returns:
            List[str]: Combined list of all skills
        """
        skills = set()
        
        # Collect skills from education
        for edu in self.education_details:
            skills.update(edu.skillsAcquired.values())
        
        # Collect skills from experience
        for exp in self.experience_details:
            skills.update(exp.skillsAcquired.values())
        
        return list(skills)

    def __str__(self) -> str:
        """
        Generate a formatted string representation of the resume.
        
        Returns:
            str: Complete formatted resume text
        """
        def format_dict(dict_obj: Dict[str, str]) -> str:
            """Helper function to format dictionary as string."""
            return "\n".join(f"    {key}: {value}" for key, value in dict_obj.items())

        def format_dataclass(obj) -> str:
            """Helper function to format dataclass as string."""
            return "\n".join(f"  {field.name}: {getattr(obj, field.name)}" 
                           for field in obj.__dataclass_fields__.values())

        return (
            "=== RESUME ===\n\n"
            "Personal Information:\n" + format_dataclass(self.personal_information) + "\n\n"
            "Self Identification:\n" + format_dataclass(self.self_identification) + "\n\n"
            "Legal Authorization:\n" + format_dataclass(self.legal_authorization) + "\n\n"
            "Work Preferences:\n" + format_dataclass(self.work_preferences) + "\n\n"
            "Education Details:\n" + "\n".join(
                f"  - {edu.degree} in {edu.fieldOfStudy} from {edu.university}\n"
                f"    GPA: {edu.gpa}, Graduation Year: {edu.graduationYear}\n"
                f"    Skills Acquired:\n{format_dict(edu.skillsAcquired)}"
                for edu in self.education_details
            ) + "\n\n"
            "Experience Details:\n" + "\n".join(
                f"  - {exp.position} at {exp.company} ({exp.employmentPeriod})\n"
                f"    Location: {exp.location}, Industry: {exp.industry}\n"
                f"    Key Responsibilities:\n{format_dict(exp.keyResponsibilities)}\n"
                f"    Skills Acquired:\n{format_dict(exp.skillsAcquired)}"
                for exp in self.experience_details
            ) + "\n\n"
            "Projects:\n" + "\n".join(f"  - {proj}" for proj in self.projects.values()) + "\n\n"
            f"Availability: {self.availability.noticePeriod}\n\n"
            f"Salary Expectations: {self.salary_expectations.salaryRangeUSD}\n\n"
            "Certifications:\n  - " + "\n  - ".join(self.certifications) + "\n\n"
            "Languages:\n" + "\n".join(
                f"  - {lang.language} ({lang.proficiency})"
                for lang in self.languages
            ) + "\n\n"
            "Interests:\n  - " + "\n  - ".join(self.interests)
        )
