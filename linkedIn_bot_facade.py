"""
LinkedIn Bot Facade - Main Bot Orchestration

This module provides a high-level interface for coordinating all LinkedIn bot components.
It manages the initialization and interaction between the authenticator, job manager,
resume handler, and GPT-powered question answering system.

The facade pattern ensures proper component initialization order and provides a clean
interface for starting the job application process.

Date: 2025
"""


class LinkedInBotFacade:
    """
    Facade class that orchestrates all LinkedIn bot components.
    
    This class manages the initialization and coordination of:
    - LinkedIn authentication
    - Resume processing  
    - GPT-powered question answering
    - Job search and application management
    
    The facade ensures components are initialized in the correct order and
    provides a simplified interface for the main application flow.
    """

    def __init__(self, login_component, apply_component):
        """
        Initialize the LinkedIn bot facade with required components.
        
        Args:
            login_component: LinkedInAuthenticator instance for handling login
            apply_component: LinkedInJobManager instance for job applications
        """
        self.login_component = login_component
        self.apply_component = apply_component
        
        # Track initialization state of various components
        self.state = {
            "credentials_set": False,
            "api_key_set": False,
            "resume_set": False,
            "gpt_answerer_set": False,
            "parameters_set": False,
            "logged_in": False
        }

    def set_resume(self, resume):
        """
        Set the resume object for the bot.
        
        Args:
            resume: Resume instance containing processed resume data
            
        Raises:
            ValueError: If resume is None or empty
        """
        if not resume:
            raise ValueError("Plain text resume cannot be empty.")
        self.resume = resume
        self.state["resume_set"] = True

    def set_secrets(self, email, password):
        """
        Set login credentials for LinkedIn authentication.
        
        Args:
            email: LinkedIn account email address
            password: LinkedIn account password
            
        Raises:
            ValueError: If email or password is missing
        """
        if not email or not password:
            raise ValueError("Email and password cannot be empty.")
        self.email = email
        self.password = password
        self.state["credentials_set"] = True

    def set_gpt_answerer(self, gpt_answerer_component):
        """
        Set the GPT answering component for intelligent form filling.
        
        Args:
            gpt_answerer_component: GPTAnswerer instance for question answering
        """
        self.gpt_answerer = gpt_answerer_component 
        self.gpt_answerer.set_resume(self.resume)
        self.apply_component.set_gpt_answerer(self.gpt_answerer)
        self.state["gpt_answerer_set"] = True

    def set_parameters(self, parameters):
        """
        Set configuration parameters for job search and application.
        
        Args:
            parameters: Dictionary containing configuration parameters
            
        Raises:
            ValueError: If parameters is None or empty
        """
        if not parameters:
            raise ValueError("Parameters cannot be None or empty.")
        self.parameters = parameters
        self.apply_component.set_parameters(parameters)
        self.state["parameters_set"] = True

    def start_login(self):
        """
        Initiate the LinkedIn login process.
        
        Raises:
            ValueError: If credentials are not set before attempting login
        """
        if not self.state["credentials_set"]:
            raise ValueError("Email and password must be set before logging in.")
        self.login_component.set_secrets(self.email, self.password)
        self.login_component.start()
        self.state["logged_in"] = True

    def start_apply(self):
        """
        Start the job application process.
        
        This method initiates the complete job search and application workflow
        after ensuring all required components are properly initialized.
        
        Raises:
            ValueError: If required components are not set before starting application
        """
        # Validate all required components are initialized
        if not self.state["logged_in"]:
            raise ValueError("You must be logged in before applying.")
        if not self.state["resume_set"]:
            raise ValueError("Plain text resume must be set before applying.")
        if not self.state["gpt_answerer_set"]:
            raise ValueError("GPT Answerer must be set before applying.")
        if not self.state["parameters_set"]:
            raise ValueError("Parameters must be set before applying.")
            
        # Start the job application process
        self.apply_component.start_applying()