"""
LinkedIn Authenticator - Handles LinkedIn Login Process

This module manages the authentication process for LinkedIn, including:
- Login form detection and interaction
- Multi-factor authentication handling  
- Session validation and maintenance
- Error handling for common login issues

The authenticator uses Selenium WebDriver to interact with LinkedIn's login interface
and handles various authentication scenarios including 2FA challenges.

Date: 2025
"""

import time
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from logging_config import logger


class LinkedInAuthenticator:
    """
    Handles LinkedIn authentication process using Selenium WebDriver.
    
    This class manages the complete login workflow including:
    - Initial login form submission
    - Multi-factor authentication challenges
    - Session validation  
    - Error detection and handling
    """
    
    def __init__(self, driver=None):
        """
        Initialize the LinkedIn authenticator.
        
        Args:
            driver: Selenium WebDriver instance for browser automation
        """
        self.driver = driver
        self.email = ""
        self.password = ""

    def set_secrets(self, email: str, password: str) -> None:
        """
        Set login credentials for authentication.
        
        Args:
            email: LinkedIn account email address
            password: LinkedIn account password
        """
        self.email = email
        self.password = password

    def start(self) -> None:
        """
        Start the authentication process by navigating to LinkedIn and logging in.
        
        This method initiates the complete login workflow:
        1. Navigate to LinkedIn homepage
        2. Check if already logged in
        3. Handle login process if needed
        """
        logger.info("[AUTH] Starting LinkedIn authentication process")
        logger.debug("[AUTH] Navigating to LinkedIn homepage...")
        
        try:
            self.driver.get('https://www.linkedin.com')
            logger.debug("[AUTH] Successfully navigated to LinkedIn.com")
        except Exception as e:
            logger.error(f"[AUTH ERROR] Failed to navigate to LinkedIn: {e}")
            raise
        
        self.wait_for_page_load()
        logger.debug("[AUTH] Page load complete")
        
        if not self.is_logged_in():
            logger.info("[AUTH] Not logged in, initiating login process...")
            self.handle_login()
        else:
            logger.info("[AUTH] Already logged in to LinkedIn")
            logger.debug(f"[AUTH] Current URL: {self.driver.current_url}")

    def handle_login(self) -> None:
        """
        Handle the complete LinkedIn login process.
        
        This method manages the login workflow including credential entry,
        form submission, and post-login security checks.
        """
        logger.info("[AUTH] Starting login workflow")
        logger.debug("[AUTH] Navigating to login page...")
        
        try:
            self.driver.get("https://www.linkedin.com/login")
            logger.debug("[AUTH] Successfully navigated to login page")
        except Exception as e:
            logger.error(f"[AUTH ERROR] Failed to navigate to login page: {e}")
            raise
        
        try:
            # Enter credentials and submit form
            logger.debug("[AUTH] Entering credentials")
            self.enter_credentials()
            
            logger.debug("[AUTH] Submitting login form")
            self.submit_login_form()
            
            # Wait for login to process
            logger.debug("[AUTH] Waiting for login to process (8 seconds)")
            time.sleep(8)  # Allow time for login processing and redirects
            
            # Handle any security challenges
            logger.debug("[AUTH] Checking for security challenges")
            self.handle_security_check()
            
            logger.info("[AUTH] Login workflow completed successfully")
            
        except NoSuchElementException as e:
            logger.error(f"[AUTH ERROR] Login failed - element not found: {e}")
            logger.error("[AUTH ERROR] Could not log in to LinkedIn. Please check your credentials.")
            raise

    def enter_credentials(self) -> None:
        """
        Enter email and password into the LinkedIn login form.
        
        Raises:
            TimeoutException: If login form elements are not found within timeout
        """
        try:
            logger.debug("Entering login credentials...")
            
            # Wait for and fill email field
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Fill password field
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            logger.debug("Credentials entered successfully")
            
        except TimeoutException:
            logger.error("LinkedInAuthenticator.enter_credentials - Login form not found. Aborting login.")
            raise

    def submit_login_form(self) -> None:
        """
        Submit the LinkedIn login form by clicking the submit button.
        
        Raises:
            NoSuchElementException: If login button is not found
        """
        try:
            logger.debug("Submitting login form...")
            login_button = self.driver.find_element(By.XPATH, '//button[@type="submit"]')
            login_button.click()
            logger.debug("Login form submitted successfully")
            
        except NoSuchElementException:
            logger.error("LinkedInAuthenticator.submit_login_form - Login button not found. Please verify the page structure.")
            raise

    def handle_security_check(self, max_wait_minutes: int = 5) -> None:
        """
        Handle LinkedIn security challenges such as captcha or verification codes.
        
        This method waits for the user to manually complete security challenges
        in the browser and monitors for successful completion.
        
        Args:
            max_wait_minutes: Maximum time to wait for security check completion
            
        Raises:
            RuntimeError: If security checkpoint is not resolved within the timeout
        """
        logger.debug("Checking for security challenges...")
        end_time = time.time() + max_wait_minutes * 60
        
        while time.time() < end_time:
            current_url = self.driver.current_url
            
            # Check if we've successfully reached the feed page
            if "/feed" in current_url:
                logger.info("Security check cleared - landed on the feed page")
                return
                
            # Check if we're on a checkpoint page
            if "/checkpoint/" in current_url:
                logger.warning("Security checkpoint detected. Please solve it in the open browser tab...")
                logger.info("Waiting for manual completion...")
                
            time.sleep(5)

        raise RuntimeError("Login aborted: security checkpoint not passed within time limit")

    def is_logged_in(self) -> bool:
        """
        Check if the user is already logged in to LinkedIn.
        
        This method navigates to the LinkedIn feed and looks for elements
        that indicate a successful login state.
        
        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            logger.debug("Checking if already logged in...")
            self.driver.get('https://www.linkedin.com/feed')
            
            # Look for the "Start a post" button which indicates logged-in state
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'share-box-feed-entry__trigger'))
            )
            
            buttons = self.driver.find_elements(By.CLASS_NAME, 'share-box-feed-entry__trigger')
            for button in buttons:
                if 'start a post' in button.text.strip().lower():
                    logger.info("User is already logged in to LinkedIn")
                    return True
                    
        except TimeoutException:
            logger.debug("Login verification elements not found")
            
        return False

    def wait_for_page_load(self, timeout: int = 10) -> None:
        """
        Wait for the page to fully load by checking document ready state.
        
        Args:
            timeout: Maximum time to wait for page load in seconds
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            logger.debug("Page loaded successfully")
            
        except TimeoutException:
            logger.warning("LinkedInAuthenticator.wait_for_page_load - Page load timed out, continuing anyway")
