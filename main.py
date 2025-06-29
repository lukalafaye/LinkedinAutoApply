"""
LinkedIn Auto Jobs Applier with AI - Main Entry Point

This module serves as the primary entry point for the LinkedIn job application automation bot.
It handles configuration validation, file management, and orchestrates the entire application
process using AI-powered form filling and intelligent job matching.

Features:
- YAML configuration validation and loading
- Resume file management (PDF and plain text)
- Bot initialization and coordination
- Comprehensive error handling and logging

Usage:
    python main.py [--resume path/to/resume.pdf]

Date: 2025
"""

import os
import re
from pathlib import Path

import click
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from gpt import GPTAnswerer
from linkedIn_authenticator import LinkedInAuthenticator
from linkedIn_bot_facade import LinkedInBotFacade
from linkedIn_job_manager import LinkedInJobManager
from logging_config import logger
from resume import Resume
from utils import chromeBrowserOptions

# Set UTF-8 encoding for proper character handling
os.environ['PYTHONIOENCODING'] = 'utf-8'


class ConfigError(Exception):
    """Custom exception for configuration-related errors."""
    pass

class ConfigValidator:
    """
    Handles validation of YAML configuration files.
    
    This class provides static methods to validate various configuration files
    including main config, secrets, and their respective parameters.
    """
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email format using regex pattern.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if email format is valid, False otherwise
        """
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, email) is not None
    
    @staticmethod
    def validate_config(config_yaml_path: Path) -> dict:
        """
        Validate the main configuration YAML file.
        
        Validates all required parameters including job search criteria,
        experience levels, job types, and filtering options.
        
        Args:
            config_yaml_path: Path to the config.yaml file
            
        Returns:
            dict: Validated configuration parameters
            
        Raises:
            ConfigError: If configuration is invalid or missing required fields
        """
        try:
            with open(config_yaml_path, 'r', encoding='utf-8') as stream:
                parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Error reading config file {config_yaml_path}: {exc}")
        except FileNotFoundError:
            raise ConfigError(f"Config file not found: {config_yaml_path}")

        # Validate 'remote' parameter
        if 'remote' not in parameters or not isinstance(parameters['remote'], bool):
            raise ConfigError(f"'remote' in config file {config_yaml_path} must be a boolean value.")

        # Validate 'experienceLevel' parameters
        experience_level = parameters.get('experienceLevel', {})
        valid_experience_levels = [
            'internship', 'entry', 'associate', 'mid-senior level', 'director', 'executive'
        ]
        for level in valid_experience_levels:
            if level not in experience_level or not isinstance(experience_level[level], bool):
                raise ConfigError(f"Experience level '{level}' must be a boolean value in config file {config_yaml_path}.")

        # Validate 'jobTypes' parameters
        job_types = parameters.get('jobTypes', {})
        valid_job_types = [
            'full-time', 'contract', 'part-time', 'temporary', 'internship', 'other', 'volunteer'
        ]
        for job_type in valid_job_types:
            if job_type not in job_types or not isinstance(job_types[job_type], bool):
                raise ConfigError(f"Job type '{job_type}' must be a boolean value in config file {config_yaml_path}.")

        # Validate 'date' filter parameters
        date = parameters.get('date', {})
        valid_dates = ['all time', 'month', 'week', '24 hours']
        for date_filter in valid_dates:
            if date_filter not in date or not isinstance(date[date_filter], bool):
                raise ConfigError(f"Date filter '{date_filter}' must be a boolean value in config file {config_yaml_path}.")

        # Validate 'positions' list
        positions = parameters.get('positions', [])
        if not isinstance(positions, list) or not all(isinstance(pos, str) for pos in positions):
            raise ConfigError(f"'positions' must be a list of strings in config file {config_yaml_path}.")
        
        # Validate 'locations' list
        locations = parameters.get('locations', [])
        if not isinstance(locations, list) or not all(isinstance(loc, str) for loc in locations):
            raise ConfigError(f"'locations' must be a list of strings in config file {config_yaml_path}.")

        # Validate 'distance' parameter
        approved_distances = {0, 5, 10, 25, 50, 100}
        distance = parameters.get('distance')
        if distance not in approved_distances:
            raise ConfigError(f"Invalid distance value in config file {config_yaml_path}. Must be one of: {approved_distances}")

        # Validate and sanitize 'companyBlacklist'
        company_blacklist = parameters.get('companyBlacklist', [])
        if not isinstance(company_blacklist, list) or not all(isinstance(comp, str) for comp in company_blacklist):
            company_blacklist = []
        parameters['companyBlacklist'] = company_blacklist

        # Validate and sanitize 'titleBlacklist'
        title_blacklist = parameters.get('titleBlacklist', [])
        if not isinstance(title_blacklist, list) or not all(isinstance(word, str) for word in title_blacklist):
            title_blacklist = []
        parameters['titleBlacklist'] = title_blacklist
        
        return parameters

    @staticmethod
    def validate_secrets(secrets_yaml_path: Path) -> tuple:
        """
        Validate the secrets YAML file containing sensitive credentials.
        
        Validates email format, password presence, and OpenAI API key.
        Uses fallback logic: tries secrets.yaml first, then secrets.example.yaml.
        
        Args:
            secrets_yaml_path: Path to the secrets file (secrets.yaml or secrets.example.yaml)
            
        Returns:
            tuple: (email, password, openai_api_key)
            
        Raises:
            ConfigError: If secrets file is invalid or missing required fields
        """
        try:
            with open(secrets_yaml_path, 'r', encoding='utf-8') as stream:
                secrets = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Error reading secrets file {secrets_yaml_path}: {exc}")
        except FileNotFoundError:
            raise ConfigError(f"Secrets file not found: {secrets_yaml_path}")

        # Check for mandatory secrets
        mandatory_secrets = ['email', 'password', 'openai_api_key']
        for secret in mandatory_secrets:
            if secret not in secrets:
                raise ConfigError(f"Missing secret in file {secrets_yaml_path}: {secret}")
           
        # Validate email format
        if not ConfigValidator.validate_email(secrets['email']):
            raise ConfigError(f"Invalid email format in secrets file {secrets_yaml_path}.")
            
        # Validate password is not empty
        if not secrets['password']:
            raise ConfigError(f"Password cannot be empty in secrets file {secrets_yaml_path}.")
            
        # Validate OpenAI API key is not empty
        if not secrets['openai_api_key']:
            raise ConfigError(f"OpenAI API key cannot be empty in secrets file {secrets_yaml_path}.")

        return secrets['email'], str(secrets['password']), secrets['openai_api_key']

class FileManager:
    """
    Handles file operations and validation for the application.
    
    This class provides static methods for finding files, validating data folders,
    and managing file paths for resumes and configuration files.
    """
    
    @staticmethod
    def find_file(name_containing: str, with_extension: str, at_path: Path) -> Path:
        """
        Find a file in a directory by name pattern and extension.
        
        Args:
            name_containing: String that should be contained in the filename
            with_extension: File extension to match (e.g., '.pdf')
            at_path: Directory path to search in
            
        Returns:
            Path: Path to the found file, or None if not found
        """
        for file in at_path.iterdir():
            if name_containing.lower() in file.name.lower() and file.suffix.lower() == with_extension.lower():
                return file
        return None

    @staticmethod
    def validate_data_folder(app_data_folder: Path) -> tuple:
        """
        Validate that the data folder exists and contains required files.
        
        Args:
            app_data_folder: Path to the application data folder
            
        Returns:
            tuple: (secrets_file, config_file, plain_text_resume_file, output_folder)
            
        Raises:
            FileNotFoundError: If data folder or required files are missing
        """
        if not app_data_folder.exists() or not app_data_folder.is_dir():
            raise FileNotFoundError(f"Data folder not found: {app_data_folder}")

        # Define required file paths with fallback for secrets
        secrets_file = app_data_folder / 'secrets.yaml'
        if not secrets_file.exists():
            secrets_file = app_data_folder / 'secrets.example.yaml'
            logger.info("secrets.yaml not found, using secrets.example.yaml as fallback")
            
        config_file = app_data_folder / 'config.yaml'
        plain_text_resume_file = app_data_folder / 'plain_text_resume.yaml'
        
        # Check for missing files
        missing_files = []
        if not secrets_file.exists():
            missing_files.append('secrets.yaml (or secrets.example.yaml)')
        if not config_file.exists():
            missing_files.append('config.yaml')
        if not plain_text_resume_file.exists():
            missing_files.append('plain_text_resume.yaml')
        
        if missing_files:
            raise FileNotFoundError(f"Missing files in the data folder: {', '.join(missing_files)}")
        
        # Create output folder if it doesn't exist
        output_folder = app_data_folder / 'output'
        output_folder.mkdir(exist_ok=True)
        
        return secrets_file, config_file, plain_text_resume_file, output_folder

    @staticmethod
    def file_paths_to_dict(resume_file: Path | None, plain_text_resume_file: Path) -> dict:
        """
        Convert file paths to dictionary format for the application.
        
        Args:
            resume_file: Optional path to PDF resume file
            plain_text_resume_file: Path to plain text resume YAML file
            
        Returns:
            dict: Dictionary containing file paths
            
        Raises:
            FileNotFoundError: If required files are missing
        """
        if not plain_text_resume_file.exists():
            raise FileNotFoundError(f"Plain text resume file not found: {plain_text_resume_file}")
        
        result = {'plainTextResume': plain_text_resume_file}
        
        if resume_file is not None:
            if not resume_file.exists():
                raise FileNotFoundError(f"Resume file not found: {resume_file}")
            result['resume'] = resume_file
        
        return result


def init_browser():
    """
    Initialize and configure Chrome WebDriver for LinkedIn automation.
    
    Returns:
        webdriver.Chrome: Configured Chrome WebDriver instance
        
    Raises:
        RuntimeError: If browser initialization fails
    """
    try:
        options = chromeBrowserOptions()
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize browser: {str(e)}")


def create_and_run_bot(email: str, password: str, parameters: dict, openai_api_key: str):
    """
    Create and execute the LinkedIn job application bot.
    
    This function initializes all bot components and orchestrates the complete
    job application process.
    
    Args:
        email: LinkedIn account email
        password: LinkedIn account password  
        parameters: Configuration parameters for job search
        openai_api_key: OpenAI API key for GPT functionality
        
    Raises:
        RuntimeError: If bot execution fails
    """
    try:
        # Initialize browser and components
        browser = init_browser()
        login_component = LinkedInAuthenticator(browser)
        apply_component = LinkedInJobManager(browser)
        gpt_answerer_component = GPTAnswerer(openai_api_key)
        
        # Load and process resume
        with open(parameters['uploads']['plainTextResume'], "r", encoding='utf-8') as file:
            plain_text_resume_file = file.read()
        resume_object = Resume(plain_text_resume_file)
        
        # Initialize and configure bot facade
        bot = LinkedInBotFacade(login_component, apply_component)
        bot.set_secrets(email, password)
        bot.set_resume(resume_object)
        bot.set_gpt_answerer(gpt_answerer_component)
        bot.set_parameters(parameters)
        
        # Execute the job application process
        bot.start_login()
        bot.start_apply()
        
    except Exception as e:
        raise RuntimeError(f"Error running the bot: {str(e)}")

@click.command()
@click.option('--resume', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path), 
              help="Path to the resume PDF file")
def main(resume: Path = None):
    """
    Main entry point for the LinkedIn job application bot.
    
    This function orchestrates the complete workflow:
    1. Validates configuration and secret files
    2. Initializes all required components
    3. Starts the automated job application process
    
    Args:
        resume: Optional path to PDF resume file. If not provided, 
                will use dynamic resume generation from plain text resume.
    """
    try:
        # Initialize data folder and validate required files
        data_folder = Path("data_folder")
        secrets_file, config_file, plain_text_resume_file, output_folder = FileManager.validate_data_folder(data_folder)
        
        # Validate configuration files
        parameters = ConfigValidator.validate_config(config_file)
        email, password, openai_api_key = ConfigValidator.validate_secrets(secrets_file)
        
        # Setup file paths for resume handling
        parameters['uploads'] = FileManager.file_paths_to_dict(resume, plain_text_resume_file)
        parameters['outputFileDirectory'] = output_folder

        # Create and run the bot
        create_and_run_bot(email, password, parameters, openai_api_key)
        
    except ConfigError as ce:
        logger.error(f"Configuration error: {str(ce)}")
        logger.error("Refer to the configuration guide for troubleshooting: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except FileNotFoundError as fnf:
        logger.error(f"File not found: {str(fnf)}")
        logger.error("Ensure all required files are present in the data folder.")
        logger.error("Refer to the file setup guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except RuntimeError as re:
        logger.error(f"Runtime error: {str(re)}")
        logger.error("Check browser setup and other runtime issues.")
        logger.error("Refer to the configuration and troubleshooting guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        logger.error("Refer to the general troubleshooting guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")


if __name__ == "__main__":
    main()
