"""
Utility Functions - Helper Functions and Browser Configuration

This module provides utility functions for the LinkedIn job application bot including:
- Chrome browser configuration and profile management
- Scroll automation for dynamic content loading
- File and path management utilities
- Color-coded console output functions
- PDF conversion utilities

These utilities support the main application functionality with commonly needed
operations and browser automation helpers.

Date: 2025
"""

import json
import os
import random
import tempfile
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from logging_config import logger


# Configuration constants
HEADLESS = False  # Set to True to run browser in headless mode
CHROME_PROFILE_PATH = os.path.join(os.getcwd(), "chrome_profile", "linkedin_profile")


def ensure_chrome_profile() -> str:
    """
    Ensure Chrome profile directory exists for persistent browser sessions.
    
    Creates the Chrome profile directory structure if it doesn't exist,
    allowing the bot to maintain login sessions and preferences across runs.
    
    Returns:
        str: Path to the Chrome profile directory
    """
    profile_dir = os.path.dirname(CHROME_PROFILE_PATH)
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
    if not os.path.exists(CHROME_PROFILE_PATH):
        os.makedirs(CHROME_PROFILE_PATH)
    return CHROME_PROFILE_PATH


def is_scrollable(element) -> bool:
    """
    Check if a web element is scrollable.
    
    Determines if an element has scrollable content by comparing
    its scroll height to its client height.
    
    Args:
        element: Selenium WebElement to check
        
    Returns:
        bool: True if element is scrollable, False otherwise
    """
    try:
        scroll_height = int(element.get_attribute("scrollHeight") or 0)
        client_height = int(element.get_attribute("clientHeight") or 0)
        return scroll_height > client_height
    except (ValueError, TypeError):
        return False


def scroll_slow(
    driver, 
    scrollable_element, 
    start: int = 0, 
    end: int = 3600, 
    step: int = 100, 
    reverse: bool = False
) -> None:
    """
    Perform slow, human-like scrolling on a web element.
    
    This function simulates natural scrolling behavior to avoid detection
    by anti-bot systems. It scrolls incrementally with random delays.
    
    Args:
        driver: Selenium WebDriver instance
        scrollable_element: WebElement to scroll within
        start: Starting scroll position in pixels
        end: Ending scroll position in pixels  
        step: Scroll increment in pixels
        reverse: If True, scroll from end to start
        
    Raises:
        ValueError: If step is zero
    """
    if reverse:
        start, end = end, start
        step = -step
        
    if step == 0:
        raise ValueError("Step cannot be zero.")
        
    # Check if element is scrollable
    try:
        if not scrollable_element.is_displayed():
            logger.warning("Element is not visible, skipping scroll")
            return
            
        if not is_scrollable(scrollable_element):
            logger.warning("Element is not scrollable")
            return
            
        # Validate scroll range
        if (step > 0 and start >= end) or (step < 0 and start <= end):
            logger.warning("Invalid scroll range, no scrolling will occur")
            return
        
        # Perform incremental scrolling
        script_scroll_to = "arguments[0].scrollTop = arguments[1];"
        for position in range(start, end, step):
            try:
                driver.execute_script(script_scroll_to, scrollable_element, position)
                # Add small random delay to simulate human behavior
                time.sleep(random.uniform(0.1, 0.3))
            except Exception as e:
                logger.error(f"Error during scrolling at position {position}: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error in scroll_slow: {e}")
    except Exception as e:
        logger.exception(f"Exception occurred: {e}")


def HTML_to_PDF(file_path: str) -> str:
    """
    Convert HTML file to PDF using Chrome's print-to-PDF functionality.
    
    This function loads an HTML file in Chrome and converts it to PDF format
    using Chrome DevTools Protocol commands.
    
    Args:
        file_path: Path to the HTML file to convert
        
    Returns:
        str: Base64-encoded PDF data
        
    Raises:
        FileNotFoundError: If the specified HTML file doesn't exist
        RuntimeError: If WebDriver encounters an error
        TimeoutError: If PDF generation takes too long
    """
    # Validate and prepare file paths
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The specified file does not exist: {file_path}")
    
    file_url = f"file:///{os.path.abspath(file_path).replace(os.sep, '/')}"
    
    # Set up Chrome options for PDF generation
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')  # Run headless for PDF generation
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Initialize Chrome driver
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Load the HTML file
        driver.get(file_url)
        time.sleep(3)  # Allow page to fully load
        
        start_time = time.time()
        
        # Generate PDF using Chrome DevTools Protocol
        pdf_base64 = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "landscape": False,
            "paperWidth": 8.5,  # US Letter width in inches
            "paperHeight": 11,  # US Letter height in inches
            "marginTop": 0.4,
            "marginBottom": 0.4,
            "marginLeft": 0.4,
            "marginRight": 0.4,
            "displayHeaderFooter": False,
            "preferCSSPageSize": True,
            "generateDocumentOutline": False,
            "generateTaggedPDF": False,
            "transferMode": "ReturnAsBase64"
        })
        
        # Check for timeout
        if time.time() - start_time > 120:
            raise TimeoutError("PDF generation exceeded the 120-second timeout limit")
            
        return pdf_base64['data']

    except WebDriverException as e:
        raise RuntimeError(f"WebDriver exception occurred during PDF generation: {e}")
    
    finally:
        # Ensure the driver is properly closed
        driver.quit()


def chromeBrowserOptions():
    """
    Configure Chrome browser options for LinkedIn automation.
    
    Returns optimized Chrome options for web scraping and automation,
    including anti-detection measures and performance optimizations.
    
    Returns:
        webdriver.ChromeOptions: Configured Chrome options
    """
    options = webdriver.ChromeOptions()
    
    # Basic Chrome options
    options.add_argument('--no-sandbox')
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-extensions")
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')
    
    # Headless mode (controlled by global HEADLESS constant)
    if HEADLESS:
        options.add_argument("--headless")
    
    # Window and display options
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Anti-detection measures
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    # User agent to appear more like a regular browser
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Ensure Chrome profile directory exists
    ensure_chrome_profile()
    
    # Use temporary profile for each session to avoid conflicts
    tmp_profile = tempfile.mkdtemp(prefix='linkedin_bot_profile_')
    options.add_argument(f'--user-data-dir={tmp_profile}')
        
    return options


def log_error(text: str) -> None:
    """
    Log text as error message.
    
    Args:
        text: Text to log as error
    """
    logger.error(text)


def log_warning(text: str) -> None:
    """
    Log text as warning message.
    
    Args:
        text: Text to log as warning
    """
    logger.warning(text)


def log_success(text: str) -> None:
    """
    Log text as info message (for success cases).
    
    Args:
        text: Text to log as success info
    """
    logger.info(text)