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
        # Check for basic email format and reject emails with consecutive dots
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return False
        
        # Reject emails with consecutive dots (like test..test@domain.com)
        if '..' in email:
            return False
            
        return True
    
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
    def find_file_by_name(name_containing: str, with_extension: str, at_path: Path) -> Path:
        """
        Find a file by name pattern and extension in a directory.
        
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
        
        Supports both new resume format (resume.yaml) and legacy format 
        (plain_text_resume.yaml) for backward compatibility with tests.
        
        Args:
            app_data_folder: Path to the application data folder
            
        Returns:
            tuple: (secrets_file, config_file, resume_file, output_folder)
            
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
        
        # Try new format first, then legacy format for backward compatibility
        resume_file = app_data_folder / 'resume.yaml'
        if not resume_file.exists():
            resume_file = app_data_folder / 'plain_text_resume.yaml'
            if resume_file.exists():
                logger.info("Using legacy resume format: plain_text_resume.yaml")
        
        # Check for missing files
        missing_files = []
        if not secrets_file.exists():
            missing_files.append('secrets.yaml (or secrets.example.yaml)')
        if not config_file.exists():
            missing_files.append('config.yaml')
        if not resume_file.exists():
            missing_files.append('resume.yaml (or plain_text_resume.yaml)')
        
        if missing_files:
            raise FileNotFoundError(f"Missing files in the data folder: {', '.join(missing_files)}")
        
        if resume_file.name == 'resume.yaml':
            logger.info("Using new resume format: resume.yaml")
        
        # Create output folder if it doesn't exist
        output_folder = app_data_folder / 'output'
        output_folder.mkdir(exist_ok=True)
        
        return secrets_file, config_file, resume_file, output_folder

    @staticmethod
    def file_paths_to_dict(resume_file: Path | None, resume_yaml_file: Path) -> dict:
        """
        Convert file paths to dictionary format for the application.
        
        Args:
            resume_file: Optional path to PDF resume file
            resume_yaml_file: Path to resume YAML file (new or legacy format)
            
        Returns:
            dict: Dictionary containing file paths
            
        Raises:
            FileNotFoundError: If required files are missing
        """
        if not resume_yaml_file.exists():
            raise FileNotFoundError(f"Resume YAML file not found: {resume_yaml_file}")
        
        result = {'plainTextResume': resume_yaml_file}
        
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
    job application process using the new JSON Resume format.
    
    Args:
        email: LinkedIn account email
        password: LinkedIn account password  
        parameters: Configuration parameters for job search
        openai_api_key: OpenAI API key for GPT functionality
        
    Raises:
        RuntimeError: If bot execution fails
    """
    logger.info("[BOT INIT] Starting bot initialization")
    
    try:
        # Initialize browser and components
        logger.info("[BOT INIT] Initializing Chrome browser")
        browser = init_browser()
        logger.debug(f"[BOT INIT] Browser initialized successfully, session ID: {browser.session_id}")
        
        logger.info("[BOT INIT] Creating authentication component")
        login_component = LinkedInAuthenticator(browser)
        
        logger.info("[BOT INIT] Creating job manager component")
        apply_component = LinkedInJobManager(browser)
        
        logger.info("[BOT INIT] Creating GPT answerer component")
        gpt_answerer_component = GPTAnswerer(openai_api_key)
        logger.debug("[BOT INIT] GPT answerer initialized with API key")
        
        # Load and process resume using new JSON Resume format
        logger.info("[BOT INIT] Loading resume file")
        resume_path = parameters['uploads']['plainTextResume']
        logger.debug(f"[BOT INIT] Resume path: {resume_path}")
        
        with open(resume_path, "r", encoding='utf-8') as file:
            resume_file_content = file.read()
        logger.debug(f"[BOT INIT] Resume file loaded, size: {len(resume_file_content)} bytes")
        
        # Load resume using updated Resume class that handles new format
        logger.info("[BOT INIT] Loading resume using updated Resume class with new YAML format")
        resume_object = Resume(resume_file_content, parameters)
        logger.debug(f"[BOT INIT] Resume parsed successfully: {resume_object.personal_information.name}")
        
        # Initialize and configure bot facade
        logger.info("[BOT INIT] Creating bot facade")
        bot = LinkedInBotFacade(login_component, apply_component)
        
        logger.debug("[BOT INIT] Configuring bot with credentials")
        bot.set_secrets(email, password)
        
        logger.debug("[BOT INIT] Setting resume in bot")
        bot.set_resume(resume_object)
        
        logger.debug("[BOT INIT] Setting GPT answerer in bot")
        bot.set_gpt_answerer(gpt_answerer_component)
        
        logger.debug("[BOT INIT] Setting search parameters in bot")
        bot.set_parameters(parameters)
        
        logger.info("[BOT INIT] Bot initialization complete, starting execution")
        logger.info("-"*80)
        
        # Execute the job application process
        logger.info("[BOT EXEC] Starting LinkedIn login")
        bot.start_login()
        logger.info("[BOT EXEC] Login completed successfully")
        
        logger.info("[BOT EXEC] Starting job application process")
        bot.start_apply()
        logger.info("[BOT EXEC] Job application process completed")
        
    except Exception as e:
        logger.error(f"[BOT ERROR] Error running the bot: {str(e)}")
        logger.exception("[BOT ERROR] Full exception traceback:")
        raise RuntimeError(f"Error running the bot: {str(e)}")

@click.command()
@click.option('--resume', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path), 
              help="Path to the resume PDF file")
@click.option('--verbose', '-v', is_flag=True, default=False,
              help="Enable verbose logging (show DEBUG messages on console)")
def main(resume: Path = None, verbose: bool = False):
    """
    Main entry point for the LinkedIn job application bot.
    
    This function orchestrates the complete workflow:
    1. Validates configuration and secret files
    2. Initializes all required components
    3. Starts the automated job application process
    
    Args:
        resume: Optional path to PDF resume file. If not provided, 
                will use dynamic resume generation from plain text resume.
        verbose: If True, enables verbose logging (DEBUG messages on console)
    """
    # [ENTRY POINT] Starting application
    logger.info("="*80)
    logger.info("LinkedIn Auto Apply Bot - Starting")
    logger.info("="*80)
    logger.debug(f"[MAIN] Command line arguments: resume={resume}, verbose={verbose}")
    
    try:
        # Configure logging based on verbose flag
        from logging_config import configure_verbose_logging
        configure_verbose_logging(verbose)
        
        if verbose:
            logger.info("Verbose logging enabled - DEBUG messages will be shown on console")
        
        logger.info("[MAIN] Starting file validation and configuration loading")
        
        # Initialize data folder and validate required files
        logger.debug("[MAIN] Initializing data folder structure")
        data_folder = Path("data_folder")
        secrets_file, config_file, resume_yaml_file, output_folder = FileManager.validate_data_folder(data_folder)
        logger.debug(f"[MAIN] Data folder validated: secrets={secrets_file}, config={config_file}, resume={resume_yaml_file}")
        
        # Validate configuration files
        logger.info("[MAIN] Validating configuration files")
        parameters = ConfigValidator.validate_config(config_file)
        logger.debug(f"[MAIN] Configuration loaded: positions={len(parameters.get('positions', []))}, locations={len(parameters.get('locations', []))}")
        
        logger.info("[MAIN] Validating secrets")
        email, password, openai_api_key = ConfigValidator.validate_secrets(secrets_file)
        logger.debug(f"[MAIN] Secrets validated: email={email[:3]}***@{email.split('@')[1] if '@' in email else 'unknown'}")
        
        # Setup file paths for resume handling
        logger.debug("[MAIN] Setting up resume file paths")
        parameters['uploads'] = FileManager.file_paths_to_dict(resume, resume_yaml_file)
        parameters['outputFileDirectory'] = output_folder
        logger.debug(f"[MAIN] Output directory: {output_folder}")

        # Create and run the bot
        logger.info("[MAIN] Initializing bot components")
        create_and_run_bot(email, password, parameters, openai_api_key)
        
        logger.info("="*80)
        logger.info("[MAIN] Bot execution completed successfully")
        logger.info("="*80)
        
    except ConfigError as ce:
        logger.error(f"[MAIN ERROR] Configuration error: {str(ce)}")
        logger.error("Refer to the configuration guide for troubleshooting: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except FileNotFoundError as fnf:
        logger.error(f"[MAIN ERROR] File not found: {str(fnf)}")
        logger.error("Ensure all required files are present in the data folder.")
        logger.error("Refer to the file setup guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except RuntimeError as re:
        logger.error(f"[MAIN ERROR] Runtime error: {str(re)}")
        logger.error("Check browser setup and other runtime issues.")
        logger.error("Refer to the configuration and troubleshooting guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except Exception as e:
        logger.error(f"[MAIN ERROR] An unexpected error occurred: {str(e)}")
        logger.exception("[MAIN ERROR] Full exception traceback:")
        logger.error("Refer to the general troubleshooting guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")


if __name__ == "__main__":
    main()
