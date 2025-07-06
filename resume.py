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
resume data from YAML files in the new JSON Resume schema format.

Date: 2025
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import yaml
from datetime import datetime


@dataclass
class PersonalInformation:
    """
    Container for personal contact information and details.
    
    Attributes:
        name: First name
        surname: Last name
        dateOfBirth: Date of birth in DD/MM/YYYY format
        country: Country of residence
        city: City of residence
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
        degree: Degree title and level (using 'area' field from new format)
        university: Institution name
        graduationYear: Year of graduation
        fieldOfStudy: Field or area of study
        skillsAcquired: Skills learned (empty dict for compatibility)
    """
    degree: str
    university: str
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
        industry: Industry sector (empty for compatibility)
        keyResponsibilities: Dictionary of key responsibilities and achievements
        skillsAcquired: Dictionary of skills gained during this role (empty for compatibility)
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
    
    This class loads resume data from the new YAML format and provides structured
    access to all resume sections including personal information, experience,
    education, skills, and preferences. It converts the new format to the old
    expected format for compatibility with existing GPT templates.
    """
    
    def __init__(self, yaml_str: str, config_data: Optional[Dict] = None):
        """
        Initialize resume from new YAML format string content.
        
        Args:
            yaml_str: YAML-formatted string containing resume data in new format
            config_data: Optional config dictionary containing meta information
            
        Raises:
            yaml.YAMLError: If YAML content is malformed
            KeyError: If required resume sections are missing
        """
        self.config_data = config_data or {}
        try:
            data = yaml.safe_load(yaml_str)
            
            # Load personal information from basics section
            self.personal_information = self._convert_personal_information(data)
            
            # Load meta information from config
            self.self_identification = self._convert_self_identification()
            self.legal_authorization = self._convert_legal_authorization()
            self.work_preferences = self._convert_work_preferences()
            self.availability = self._convert_availability()
            self.salary_expectations = self._convert_salary_expectations()
            
            # Load education details
            self.education_details = self._convert_education_details(data.get('education', []))
            
            # Load experience details
            self.experience_details = self._convert_experience_details(data.get('work', []))
            
            # Load projects
            self.projects = self._convert_projects(data.get('projects', []))
            
            # Load certifications
            self.certifications = self._convert_certifications(data.get('certificates', []))
            
            # Load languages
            self.languages = self._convert_languages(data.get('skills', []))
            
            # Load interests/hobbies
            self.interests = self._convert_interests(data.get('hobbies', []))
            
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse resume YAML: {e}")
        except (KeyError, TypeError) as e:
            raise KeyError(f"Error processing resume data: {e}")
    
    def _convert_personal_information(self, data: Dict) -> PersonalInformation:
        """Convert basics section to PersonalInformation."""
        basics = data.get('basics', {})
        
        # Split name into first and last name
        full_name = basics.get('name', '')
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        # Extract phone prefix and number
        phone_str = basics.get('phone', '').strip()
        phone_prefix = ""
        phone_number = ""
        if phone_str.startswith('+'):
            parts = phone_str.split(' ', 1)
            if len(parts) >= 2:
                phone_prefix = parts[0]
                phone_number = parts[1].replace(' ', '').replace('-', '')
            else:
                phone_prefix = phone_str[:3] if len(phone_str) >= 3 else phone_str
                phone_number = phone_str[3:].replace(' ', '').replace('-', '')
        else:
            phone_number = phone_str.replace(' ', '').replace('-', '')
        
        # Get location info
        location = basics.get('location', {})
        city = location.get('city', '')
        country_code = location.get('countryCode', '')
        # Convert country code to country name
        country_map = {'FR': 'France', 'US': 'United States', 'IT': 'Italy', 'CA': 'Canada', 'AU': 'Australia'}
        country = country_map.get(country_code, country_code)
        
        # Extract profile URLs
        github_url = ""
        linkedin_url = ""
        for profile in basics.get('profiles', []):
            if profile.get('network', '').lower() == 'github':
                github_url = profile.get('url', '')
            elif profile.get('network', '').lower() == 'linkedin':
                linkedin_url = profile.get('url', '')
        
        # Get date of birth from config
        date_of_birth = ""
        if self.config_data.get('resume_config', {}).get('personal_details', {}).get('date_of_birth'):
            date_of_birth = self.config_data['resume_config']['personal_details']['date_of_birth']
        
        return PersonalInformation(
            name=first_name,
            surname=last_name,
            dateOfBirth=date_of_birth,
            country=country,
            city=city,
            phone=phone_number,
            phonePrefix=phone_prefix,
            email=basics.get('email', ''),
            github=github_url,
            linkedin=linkedin_url
        )
    
    def _convert_self_identification(self) -> SelfIdentification:
        """Convert config personal_details to SelfIdentification."""
        personal_details = self.config_data.get('resume_config', {}).get('personal_details', {})
        
        return SelfIdentification(
            gender=personal_details.get('gender', ''),
            pronouns=personal_details.get('pronouns', ''),
            veteran=str(personal_details.get('veteran', '')),
            disability=str(personal_details.get('disability', '')),
            ethnicity=personal_details.get('ethnicity', '')
        )
    
    def _convert_legal_authorization(self) -> LegalAuthorization:
        """Convert config legal_authorization to LegalAuthorization."""
        legal_auth = self.config_data.get('resume_config', {}).get('legal_authorization', {})
        
        return LegalAuthorization(
            euWorkAuthorization=str(legal_auth.get('eu_work_authorization', '')),
            usWorkAuthorization=str(legal_auth.get('us_work_authorization', '')),
            requiresUsVisa=str(legal_auth.get('requires_us_visa', '')),
            legallyAllowedToWorkInUs=str(legal_auth.get('legally_allowed_to_work_in_us', '')),
            requiresUsSponsorship=str(legal_auth.get('requires_us_sponsorship', '')),
            requiresEuVisa=str(legal_auth.get('requires_eu_visa', '')),
            legallyAllowedToWorkInEu=str(legal_auth.get('legally_allowed_to_work_in_eu', '')),
            requiresEuSponsorship=str(legal_auth.get('requires_eu_sponsorship', ''))
        )
    
    def _convert_work_preferences(self) -> WorkPreferences:
        """Convert config work_preferences to WorkPreferences."""
        work_prefs = self.config_data.get('resume_config', {}).get('work_preferences', {})
        
        return WorkPreferences(
            remoteWork=str(work_prefs.get('remote_work', '')),
            inPersonWork=str(work_prefs.get('in_person_work', '')),
            openToRelocation=str(work_prefs.get('open_to_relocation', '')),
            willingToCompleteAssessments=str(work_prefs.get('willing_to_complete_assessments', '')),
            willingToUndergoDrugTests=str(work_prefs.get('willing_to_undergo_drug_tests', '')),
            willingToUndergoBackgroundChecks=str(work_prefs.get('willing_to_undergo_background_checks', ''))
        )
    
    def _convert_availability(self) -> Availability:
        """Convert config availability to Availability."""
        availability = self.config_data.get('resume_config', {}).get('availability', {})
        
        return Availability(
            noticePeriod=availability.get('notice_period', '')
        )
    
    def _convert_salary_expectations(self) -> SalaryExpectations:
        """Convert config salary_expectations to SalaryExpectations."""
        salary = self.config_data.get('resume_config', {}).get('salary_expectations', {})
        
        return SalaryExpectations(
            salaryRangeUSD=str(salary.get('salary_range_usd', ''))
        )
    
    def _convert_education_details(self, education_data: List[Dict]) -> List[Education]:
        """Convert education array to Education list."""
        result = []
        
        for edu in education_data:
            # Extract graduation year from endDate or estimate from startDate
            graduation_year = ""
            if edu.get('endDate'):
                try:
                    graduation_year = str(datetime.fromisoformat(edu['endDate']).year)
                except:
                    if '-' in edu['endDate']:
                        graduation_year = str(int(edu['endDate'].split('-')[0]))
                    else:
                        graduation_year = str(edu['endDate'])
            elif edu.get('startDate'):
                try:
                    start_year = datetime.fromisoformat(edu['startDate']).year
                    # Estimate graduation year based on education type
                    area = (edu.get('area', '')).lower()
                    if 'master' in area:
                        graduation_year = str(start_year + 2)
                    elif 'exchange' in area:
                        graduation_year = str(start_year + 1)
                    elif 'preparation' in area or 'intensive' in area:
                        graduation_year = str(start_year + 2)
                    elif 'baccalauréat' in area or 'high school' in area:
                        graduation_year = str(start_year + 2)
                    else:
                        graduation_year = str(start_year + 3)  # Bachelor's estimation
                except:
                    if '-' in edu['startDate']:
                        start_year = int(edu['startDate'].split('-')[0])
                        graduation_year = str(start_year + 2)
            
            result.append(Education(
                degree=edu.get('area', ''),
                university=edu.get('institution', ''),
                graduationYear=graduation_year,
                fieldOfStudy=edu.get('area', ''),
                skillsAcquired={}  # Empty for compatibility
            ))
        
        return result
    
    def _convert_experience_details(self, work_data: List[Dict]) -> List[Experience]:
        """Convert work array to Experience list."""
        result = []
        
        for work in work_data:
            # Convert highlights to responsibilities
            responsibilities = {}
            for i, highlight in enumerate(work.get('highlights', [])[:3], 1):
                responsibilities[f'responsibility{i}'] = highlight
            
            # Format employment period
            employment_period = ""
            if work.get('startDate'):
                start = self._format_date(work['startDate'])
                if work.get('endDate'):
                    end = self._format_date(work['endDate'])
                    employment_period = f"{start} - {end}"
                else:
                    employment_period = f"{start} - Present"
            
            result.append(Experience(
                position=work.get('position', ''),
                company=work.get('name', ''),
                employmentPeriod=employment_period,
                location=work.get('location', ''),
                industry='',  # Empty for compatibility
                keyResponsibilities=responsibilities,
                skillsAcquired={}  # Empty for compatibility
            ))
        
        return result
    
    def _format_date(self, date_str: str) -> str:
        """Format ISO date to MM/YYYY format."""
        try:
            date_obj = datetime.fromisoformat(date_str)
            return f"{date_obj.month:02d}/{date_obj.year}"
        except:
            return date_str
    
    def _convert_projects(self, projects_data: List[Dict]) -> Dict[str, str]:
        """Convert projects array to dict format."""
        result = {}
        for i, project in enumerate(projects_data, 1):
            description = project.get('description', project.get('name', ''))
            result[f'project{i}'] = description
        return result
    
    def _convert_certifications(self, certificates_data: List[Dict]) -> List[str]:
        """Convert certificates array to string list."""
        return [cert.get('name', '') for cert in certificates_data if cert.get('name')]
    
    def _convert_languages(self, skills_data: List[Dict]) -> List[Language]:
        """Convert languages from skills section."""
        result = []
        
        # Find the Languages skill section
        for skill in skills_data:
            if skill.get('name', '').lower() == 'languages':
                # Parse language keywords like "French: Native", "English: Fluent/C2"
                for keyword in skill.get('keywords', []):
                    if ':' in keyword:
                        lang_parts = keyword.split(':', 1)
                        language = lang_parts[0].strip()
                        proficiency_raw = lang_parts[1].strip()
                        
                        # Extract proficiency level (remove additional info like /C2)
                        proficiency = proficiency_raw.split('/')[0].strip()
                        
                        result.append(Language(
                            language=language,
                            proficiency=proficiency
                        ))
        
        return result
    
    def _convert_interests(self, hobbies_data: List[Dict]) -> List[str]:
        """Convert hobbies array to interests list."""
        return [hobby.get('description', '') for hobby in hobbies_data if hobby.get('description')]

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
                f"    Graduation Year: {edu.graduationYear}\n"
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
