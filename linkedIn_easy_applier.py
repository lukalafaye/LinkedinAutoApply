"""
LinkedIn Easy Apply Bot - Application Form Handler

This module contains the core application form handling logic for the LinkedIn Easy Apply bot.
It manages the multi-step application process, form field detection and filling, file uploads,
and interaction with AI services for intelligent form completion.

Key Features:
- Multi-step form navigation and completion
- AI-powered question answering with persistent memory
- Automatic file upload handling (resume, cover letters)
- Error detection and recovery
- Support for various LinkedIn form element types (radio, dropdown, text, date, etc.)

Classes:
    LinkedInEasyApplier: Main class that handles the entire Easy Apply form submission process

Dependencies:
    - Selenium WebDriver for browser automation
    - OpenAI/GPT integration for intelligent responses
    - ReportLab for PDF generation
    - Various utility functions for browser interaction
"""

import base64
import io
import os
import random
import tempfile
import time
import traceback
import uuid
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core._api.deprecation import LangChainDeprecationWarning
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import utils
from logging_config import logger
import resume_generator

warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)    

class LinkedInEasyApplier:
    """
    LinkedIn Easy Apply Form Handler
    
    This class manages the automated completion of LinkedIn Easy Apply forms.
    It handles multi-step application processes, form field detection and filling,
    file uploads, and integrates with AI services for intelligent form completion.
    
    The class maintains a persistent memory of answers to avoid repeatedly asking
    the same questions and provides fallback strategies for various form scenarios.
    
    Attributes:
        driver: Selenium WebDriver instance for browser automation
        resume_dir: Path to resume file for upload
        set_old_answers: List of previously answered questions for reuse
        gpt_answerer: AI service for generating responses to form questions
        answers: Dictionary mapping question substrings to saved answers
    """
    
    def __init__(
        self,
        driver: Any,
        resume_dir: Optional[str],
        set_old_answers: List[Tuple[str, str, str]],
        gpt_answerer: Any,
        record_answer_cb: Optional[callable] = None,
    ):
        """
        Initialize the LinkedIn Easy Apply form handler.
        
        Args:
            driver: Selenium WebDriver instance
            resume_dir: Path to resume file for upload
            set_old_answers: List of tuples (question_type, question_text, answer)
            gpt_answerer: AI service for generating form responses
            record_answer_cb: Optional callback to persist new answers
        """
        self.driver = driver
        self.resume_dir = Path(resume_dir) if resume_dir else None
        self.set_old_answers = list(set_old_answers)
        self.gpt_answerer = gpt_answerer
        self._record_cb = record_answer_cb

        # Normalize saved answers for quick lookup
        self.set_old_answers: List[Tuple[str, str, str]] = []
        for entry in set_old_answers:
            if len(entry) == 3:
                self.set_old_answers.append(entry)
            elif len(entry) == 2:
                (q_type, q_substr), ans = entry
                self.set_old_answers.append((q_type, q_substr, ans))
            else:
                continue

        # Build quick lookup dictionary for saved answers
        self.answers: Dict[str, str] = {
            q_sub.lower().strip(): ans.title()
            for _, q_sub, ans in self.set_old_answers
        }
        logger.debug(f"Loaded saved answers: {self.answers}")

    def _remember_answer(self, qtype: str, qtext: str, answer: str) -> None:
        """
        Persist a new GPT-generated answer both in-memory and on disk.
        
        Validates that the answer is not a placeholder before saving.
        
        Args:
            qtype: Type of question (radio, text, dropdown, etc.)
            qtext: The question text
            answer: The generated answer
        """
        # Don't save placeholder values (multilingual)
        if answer:
            answer_lower = answer.lower()
            placeholders = [
                "select", "sélect", "selecciona", "seleccione",
                "choose", "choisissez", "choisir",
                "opción", "option", 
                "n/a", "none", "null",
            ]
            if any(placeholder in answer_lower for placeholder in placeholders):
                logger.warning(f"[REMEMBER] Refusing to save placeholder answer: {answer!r} for question: {qtext!r}")
                return
        
        key = (qtype.lower(), qtext.lower())
        if any((t.lower(), q.lower()) == key for t, q, _ in self.set_old_answers):
            return
        
        logger.debug(f"[REMEMBER] Saving answer: {qtype} | {qtext} → {answer}")
        self.set_old_answers.append((qtype, qtext, answer))
        self.answers[qtext.lower()] = answer
        
        if self._record_cb:
            try:
                self._record_cb(qtype, qtext, answer)
            except Exception as exc:
                logger.warning(f"Could not persist answer: {exc}")

    def _ask_openai_for_yes_no(self, prompt: str) -> str:
        """
        Get a Yes/No answer from the AI service.
        
        Args:
            prompt: The question to ask
            
        Returns:
            "Yes" or "No" response from AI
        """
        full_prompt = prompt + "\nAnswer only Yes or No."
        resp = self.gpt_answerer.openai_client.complete(prompt=full_prompt)
        logger.debug(f"OpenAI yes/no response: {resp}")
        return resp.strip().split()[0].title()

    def _get_answer_from_set(self, question_type: str, question_text: str, options: Optional[List[str]] = None) -> Optional[str]:
        """
        Look up a saved answer for the given question.
        
        Args:
            question_type: Type of question (radio, text, dropdown, etc.)
            question_text: The question text to search for
            options: Optional list of valid options for validation
            
        Returns:
            Saved answer if found and valid, None otherwise
        """
        for entry in self.set_old_answers:
            if isinstance(entry, tuple) and len(entry) == 3:
                if entry[0] == question_type and question_text in entry[1].lower():
                    answer = entry[2]
                    return answer if options is None or answer in options else None
        return None

    def _smart_dropdown_match(self, question_text: str, options: List[str]) -> Optional[str]:
        """
        Intelligently match dropdown options using resume data and pattern recognition.
        
        Handles common dropdown fields like phone country codes, emails, and other
        contact information by matching against resume data, even when field names
        are in different languages.
        
        Args:
            question_text: The question text (may be in any language)
            options: List of available dropdown options
            
        Returns:
            Best matching option from the dropdown, or None if no match found
        """
        # Normalize question text
        q_lower = question_text.lower()
        logger.debug(f"[SMART MATCH] Analyzing question: {question_text!r}")
        logger.debug(f"[SMART MATCH] Available options: {options}")
        
        # Get resume data from GPT answerer
        try:
            resume = self.gpt_answerer.resume
            if not resume:
                logger.warning("[SMART MATCH] No resume object found in gpt_answerer")
                return None
                
            # Check if resume has personal_information attribute
            if not hasattr(resume, 'personal_information'):
                logger.warning("[SMART MATCH] Resume has no 'personal_information' attribute")
                return None
                
            personal_info = resume.personal_information
            logger.debug(f"[SMART MATCH] Resume info: phone={personal_info.phone}, phonePrefix={personal_info.phonePrefix}, email={personal_info.email}, city={personal_info.city}")
            
        except Exception as e:
            logger.error(f"[SMART MATCH] Error accessing resume: {e}")
            return None
        
        # Phone country code detection (multilingual)
        phone_keywords = ["phone country", "country code", "código del país", "código país", "code pays", "ländervorwahl", "país", "country"]
        if any(kw in q_lower for kw in phone_keywords):
            logger.debug("[SMART MATCH] Detected phone country code question")
            # Use phonePrefix directly (e.g., "+33")
            country_code = personal_info.phonePrefix
            if country_code:
                logger.debug(f"[SMART MATCH] Using phone prefix from resume: {country_code}")
                
                # Try to find option containing this country code
                for option in options:
                    if country_code in option:
                        logger.info(f"[SMART MATCH] ✅ Matched country code option: {option}")
                        return option
                
                logger.warning(f"[SMART MATCH] No option found containing {country_code}")
            else:
                logger.warning(f"[SMART MATCH] No phonePrefix in resume")
        
        # Email selection (when multiple emails available)
        email_keywords = ["email", "correo", "e-mail", "courriel"]
        if any(kw in q_lower for kw in email_keywords):
            logger.debug("[SMART MATCH] Detected email question")
            resume_email = personal_info.email
            if resume_email:
                logger.debug(f"[SMART MATCH] Looking for email: {resume_email}")
                
                # Try exact match first
                for option in options:
                    if resume_email.lower() in option.lower():
                        logger.info(f"[SMART MATCH] ✅ Matched email option: {option}")
                        return option
                
                logger.warning(f"[SMART MATCH] No option found containing {resume_email}")
            else:
                logger.warning("[SMART MATCH] No email in resume")
        
        # Location/City detection
        location_keywords = ["city", "location", "ciudad", "ville", "stadt", "ubicación"]
        if any(kw in q_lower for kw in location_keywords):
            logger.debug("[SMART MATCH] Detected location question")
            city = personal_info.city
            if city:
                logger.debug(f"[SMART MATCH] Looking for city: {city}")
                
                for option in options:
                    if city.lower() in option.lower():
                        logger.info(f"[SMART MATCH] ✅ Matched location option: {option}")
                        return option
                
                logger.warning(f"[SMART MATCH] No option found containing {city}")
            else:
                logger.warning("[SMART MATCH] No city in resume")
        
        # Country detection
        country_keywords_specific = ["país", "pays", "land"] 
        if any(kw in q_lower for kw in country_keywords_specific) and "code" not in q_lower and "código" not in q_lower:
            logger.debug("[SMART MATCH] Detected country question")
            country = personal_info.country
            if country:
                logger.debug(f"[SMART MATCH] Looking for country: {country}")
                
                # Try direct match first
                for option in options:
                    if country.lower() in option.lower():
                        logger.info(f"[SMART MATCH] ✅ Matched country option: {option}")
                        return option
                
                logger.warning(f"[SMART MATCH] No option found for country {country}")
            else:
                logger.warning("[SMART MATCH] No country in resume")
        
        logger.debug("[SMART MATCH] No match found")
        return None

    def _safe_click(self, el: WebElement):
        """
        Safely click an element by defocusing, scrolling into view, and using JS click.
        
        Args:
            el: WebElement to click
        """
        # Defocus any open search input
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.2)

        # Scroll element into view
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", el
        )
        time.sleep(0.2)

        # Use JS click to avoid interception
        self.driver.execute_script("arguments[0].click();", el)
        time.sleep(0.5)

    def job_apply(self, job: Any):
        """
        Main entry point for applying to a LinkedIn job.
        
        Navigates to the job page, finds the Easy Apply button, extracts job description,
        generates a tailored resume for the specific job, and handles the complete 
        application form submission process.
        
        Args:
            job: Job object containing job details and URL
            
        Raises:
            Exception: If application process fails at any step
        """
        self.driver.get(job.link)
        
        # Store original resume path to restore later
        original_resume_dir = self.resume_dir
        
        try:
            easy_apply_button = self._find_easy_apply_button()
            job_description = self._get_job_description()
            logger.info(f"\n––––– JOB DESCRIPTION for {job.title} –––––\n{job_description}\n–––– end description ––––\n")
            job.set_job_description(job_description)
            
            # Generate tailored resume for this specific job
            tailored_resume_path = self._generate_tailored_resume(job, job_description)
            if tailored_resume_path and Path(tailored_resume_path).exists():
                # Update resume path for this job application
                self.resume_dir = Path(tailored_resume_path)
                logger.info(f"🎯 Using tailored resume: {tailored_resume_path}")
            else:
                logger.warning("Failed to generate tailored resume, using original")
            
            self._safe_click(easy_apply_button)
            self.gpt_answerer.set_job(job)
            self._fill_application_form()
            
        except Exception:
            tb_str = traceback.format_exc()
            self._discard_application()
            raise Exception(f"Failed to apply to job! Original exception: \nTraceback:\n{tb_str}")
        finally:
            # Restore original resume path for next job
            self.resume_dir = original_resume_dir

    def _stable_key(self, form_el: WebElement) -> str:
        """
        Generate a stable identifier for a form element that survives DOM recycling.
        
        Args:
            form_el: WebElement to generate key for
            
        Returns:
            Unique string identifier for the element
        """
        try:
            label = form_el.find_element(By.TAG_NAME, "label")
            return label.get_attribute("for") or label.text.strip()
        except NoSuchElementException:
            return form_el.get_attribute("outerHTML")[:120]

    def _find_easy_apply_button(self) -> WebElement:
        """
        Locate and return the clickable Easy Apply button on the job page.
        
        Returns:
            WebElement of the Easy Apply button
            
        Raises:
            Exception: If no clickable Easy Apply button is found
        """
        buttons = WebDriverWait(self.driver, 5).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, '//button[contains(@class, "jobs-apply-button") and contains(., "Easy Apply")]')
            )
        )
        
        for index, button in enumerate(buttons):
            try:
                return WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, f'(//button[contains(@class, "jobs-apply-button") and contains(., "Easy Apply")])[{index + 1}]')
                    )
                )
            except Exception:
                pass
                
        raise Exception("No clickable 'Easy Apply' button found")

    def _get_job_description(self) -> str:
        """
        Fetches and returns the full job description text from a LinkedIn job page,
        handling both the new unified two-pane layout and older layouts.
        """
        # 1) Wait for any job-details container to appear
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.jobs-description, #job-details, article.jobs-description__container"))
            )
        except TimeoutException:
            logger.error("Timed out waiting for description container")

        # 2) Expand any "show more" button if present
        try:
            more_btn = self.driver.find_element(
                By.CSS_SELECTOR,
                "button.inline-show-more-text__button, button.jobs-description__footer-button"
            )
            more_btn.click()
            time.sleep(0.5)
        except NoSuchElementException:
            pass

        # 3) Try direct #job-details (new unified pane)
        try:
            details_div = self.driver.find_element(By.ID, "job-details")
            return details_div.text.strip()
        except NoSuchElementException:
            pass

        # 4) Try article-based selector (older unified layout)
        try:
            container = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "article.jobs-description__container .jobs-box__html-content"
                ))
            )
            return container.text.strip()
        except TimeoutException:
            logger.error("Article-based selector timed out")

        # 5) Fallback to the “stretch” class
        try:
            stretch_div = self.driver.find_element(
                By.CSS_SELECTOR,
                "div.jobs-description-content__text--stretch"
            )
            return stretch_div.text.strip()
        except NoSuchElementException:
            pass

        # 6) Last resort: grab any visible text in the details container
        try:
            wrapper = self.driver.find_element(
                By.CSS_SELECTOR,
                "div.jobs-search__job-details--container, div.jobs-description"
            )
            return wrapper.text.strip()
        except Exception:
            logger.error(f"Could not locate job description:\n{traceback.format_exc()}")
            return ""


    def _auto_scroll_within_modal(self, root: WebElement):
        """
        Scroll within a modal to reveal dynamically loaded content.
        
        Args:
            root: Root element to find scrollable container within
        """
        # Find the first ancestor that scrolls
        scroller = root
        while scroller and self.driver.execute_script(
            "return arguments[0].scrollHeight <= arguments[0].clientHeight",
            scroller
        ):
            scroller = scroller.find_element(By.XPATH, "..")

        last = -1
        while True:
            self.driver.execute_script("arguments[0].scrollBy(0, 600);", scroller)
            time.sleep(0.4)  # Allow virtualized list to render
            now = self.driver.execute_script("return arguments[0].scrollTop;", scroller)
            if now == last:  # Bottom reached
                break
            last = now

    def _scroll_page(self) -> None:
        """Scroll the entire page up and down to trigger content loading."""
        scrollable_element = self.driver.find_element(By.TAG_NAME, 'html')
        utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=False)
        utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=True)

    def _fill_application_form(self) -> None:
        """
        Navigate through multi-step Easy Apply form until completion.
        
        Repeatedly scans the current form step, answers all fields,
        and advances to the next step until the application is submitted.
        """
        step = 0
        while True:
            step += 1
            logger.info(f"EASY-APPLY Step {step}")

            # --- 1️⃣  locate the *fresh* form for THIS step
            try:
                form = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "form"))
                )

                html = form.get_attribute("outerHTML")
                logger.debug("Step HTML content:")
                logger.debug(html[:5000] + (" …" if len(html) > 5000 else ""))


                # --- 2️⃣  answer every field in this form
                self._answer_visible_form(form)
            except TimeoutException:
                logger.debug("No <form> element found - assuming Review page")
                
                try:
                    # Wait for the modal to appear and be visible
                    modal = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.artdeco-modal--layer-default"))
                    )
                    # Scroll within the modal to reveal content
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", modal)
                    time.sleep(0.5)
                except TimeoutException:
                    logger.error("Modal did not appear within timeout or is not visible")

                time.sleep(0.5)

                # ✨ NEW: make sure “Follow Company” is **unchecked**
                self._unfollow_company()


            # --- 3️⃣  click Next / Review / Submit

            if self._next_or_submit():  # ⇢ returns True only on final Submit
                logger.info("Application submitted successfully ✔")

                # --- 4️⃣ Wait for the Post-submit modal (Done / Not Now button)
                try:
                    # Wait for the post-submit modal to appear
                    pop_up_modal = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.artdeco-modal.artdeco-modal--layer-default"))
                    )
                    logger.info("Pop-up modal appeared after submit")

                    # Explicitly wait for the 'Done' or 'Not now' button to appear
                    # Try multiple selectors for the post-submit modal button
                    done_button = None
                    selectors = [
                        # Modern LinkedIn layout with span text
                        (By.XPATH, "//button[.//span[normalize-space(text())='Done']] | //button[.//span[normalize-space(text())='Not now']]"),
                        # Legacy direct text
                        (By.XPATH, "//button[normalize-space(text())='Done'] | //button[normalize-space(text())='Not now']"),
                        # CSS selector for primary button in modal footer
                        (By.CSS_SELECTOR, "div.artdeco-modal__actionbar button.artdeco-button--primary"),
                        # Fallback to any button in modal footer
                        (By.CSS_SELECTOR, "div.artdeco-modal__actionbar button")
                    ]
                    
                    for selector_type, selector in selectors:
                        try:
                            done_button = WebDriverWait(pop_up_modal, 3).until(
                                EC.element_to_be_clickable((selector_type, selector))
                            )
                            logger.debug(f"Found post-submit button using selector: {selector}")
                            break
                        except TimeoutException:
                            continue
                    
                    if not done_button:
                        raise TimeoutException("Could not find post-submit modal button")

                    # Scroll the button into view to ensure visibility and interaction
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", done_button)
                    time.sleep(0.5)
                    
                    # Get button text for logging
                    button_text = done_button.text.strip() or done_button.get_attribute("aria-label") or "Done"
                    
                    # Click the 'Done' or 'Not now' button using safe click
                    self._safe_click(done_button)
                    logger.info(f"Clicked '{button_text}' button successfully")

                    # Allow time for the modal to close and wait for it to disappear
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.invisibility_of_element(pop_up_modal)
                        )
                        logger.info("Post-submit modal closed successfully")
                    except TimeoutException:
                        logger.warning("Modal did not close within timeout, continuing anyway")
                        
                    time.sleep(1)
                except TimeoutException:
                    logger.error("Timeout waiting for 'Done' or 'Not now' button or modal pop-up")
                except NoSuchElementException:
                    logger.error("Could not find 'Done' or 'Not now' button in the modal pop-up")

                break  # Exit the loop after closing the modal and proceed with the next job


    #         self.driver.execute_script(
    #             "arguments[0].scrollBy(0, 600);", form_el)
    def _answer_visible_form(self, form_el: WebElement) -> None:
        """
        Scroll inside *form_el* and keep invoking `_process_form_element`
        until no NEW elements are found **and** every visible upload <input>
        (which LI no longer wraps in data-test-form-element) is handled.
        """
        processed: set[str] = set()
        pass_idx            = 0

        while True:
            pass_idx += 1
            newly_handled = 0
            elems = form_el.find_elements(By.CSS_SELECTOR, "[data-test-form-element]")

            for el in elems:
                key = self._stable_key(el)
                if key in processed:
                    continue
                if self._process_form_element(el):
                    processed.add(key)
                    newly_handled += 1

            # ── NEW: pick up bare <input type="file"> blocks ───────────────
            for fi in form_el.find_elements(By.CSS_SELECTOR, "input[type='file']"):
                # ancestor that visually groups the upload card / button
                block = fi.find_element(
                    By.XPATH,
                    "./ancestor::div[contains(@class,'jobs-document-upload') or "  # redesign
                    "contains(@class,'js-jobs-document-upload__container')][1]"
                )
                key = self._stable_key(block)
                if key in processed:
                    continue
                if self._handle_upload_fields(block):
                    processed.add(key)
                    newly_handled += 1
            # ----------------------------------------------------------------

            logger.debug(f"Form processing pass {pass_idx}: handled {newly_handled} of "
                f"{len(elems)} + uploads (total so far {len(processed)})")

            if newly_handled == 0:
                break

            self.driver.execute_script("arguments[0].scrollBy(0, 600);", form_el)
            time.sleep(0.4)

        self._check_for_errors()

        # ensure LI re-validates the footer CTA
        modal = self.driver.find_element(By.CSS_SELECTOR,
                                        "div.jobs-easy-apply-modal__content")
        self.driver.execute_script(
            "arguments[0].scrollTo(0, arguments[0].scrollHeight);", modal)
        time.sleep(0.6)

        try:
            self.driver.switch_to.active_element.send_keys(Keys.TAB)
        except Exception:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.TAB)
        time.sleep(0.2)


    def _deep_label_text(self, root: WebElement, max_depth: int = 12) -> str:
        """
        Find the first non-empty label text within a form element using breadth-first search.
        
        This method traverses the DOM tree starting from the root element to find
        label text that describes the form element. This is essential for understanding
        what question is being asked in LinkedIn's dynamic form structure.
        
        Args:
            root: Root WebElement to search within
            max_depth: Maximum depth to search in the DOM tree
            
        Returns:
            Label text if found, empty string otherwise
        """
        queue: list[tuple[WebElement, int]] = [(root, 0)]

        while queue:
            node, depth = queue.pop(0)
            if depth > max_depth:
                break

            # Search for label elements at current level
            for lbl in node.find_elements(By.TAG_NAME, "label"):
                txt = lbl.text.strip()
                if txt:
                    return txt

            # Add children to queue for next level
            for child in node.find_elements(By.XPATH, "./*"):
                queue.append((child, depth + 1))

        return ""

    def _process_form_element(self, element: WebElement) -> bool:
        """
        Detect and handle form controls within a LinkedIn form element.
        
        This is the main dispatcher that identifies what type of form element
        we're dealing with and delegates to the appropriate handler. It can
        handle multiple control types within a single element.
        
        Args:
            element: WebElement containing form controls
            
        Returns:
            True if any controls were successfully handled, False otherwise
        """
        handled = False

        # Handle file uploads first
        if self._is_upload_field(element):
            logger.debug("Detected upload field")
            self._handle_upload_fields(element)
            handled = True

        # Handle different form control types
        handled |= self._handle_terms_of_service(element)
        handled |= self._handle_multiline_question(element)
        handled |= self._handle_radio_question(element)
        handled |= self._handle_dropdown_question(element)
        handled |= self._handle_textbox_question(element)
        handled |= self._handle_date_question(element)

        if handled:
            logger.debug("Handled at least one sub-control")
        else:
            logger.debug("No handler matched. HTML snippet:")
            logger.debug(element.get_attribute("outerHTML")[:500] + "…")

        return handled

    def _get_primary_action_button(self) -> WebElement:
        """
        Locate and return the primary action button for the Easy Apply modal.
        
        This method finds the Next/Review/Submit button that advances the application
        process. It handles LinkedIn's dynamic button states and ensures the button
        is scrolled into view and clickable.
        
        Returns:
            WebElement of the primary action button
            
        Raises:
            TimeoutException: If no clickable primary button is found
        """
        # Ensure footer is located first
        try:
            footer = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.jobs-easy-apply-modal footer"))
            )
        except TimeoutException:
            logger.error("[FOOTER] Timeout waiting for Easy Apply modal footer - application may be complete")
            # Check if we're in a post-submission state
            try:
                self.driver.find_element(By.CSS_SELECTOR, "div.artdeco-modal.artdeco-modal--layer-default")
                logger.debug("[FOOTER] Found generic modal - likely post-submission modal")
            except NoSuchElementException:
                logger.debug("[FOOTER] No modal found at all")
            raise
        # ----------------------------------------------------------------------


        locators = [
            # 1️⃣ explicit hooks
            (By.CSS_SELECTOR, 'button[data-live-test-easy-apply-next-button]'),
            (By.CSS_SELECTOR, 'button[data-live-test-easy-apply-review-button]'),
            (By.CSS_SELECTOR, 'button[data-live-test-easy-apply-submit-button]'),
            (By.CSS_SELECTOR, 'button[data-easy-apply-next-button]'),
            # 2️⃣ aria labels
            (By.CSS_SELECTOR, 'button[aria-label*="Continue to next step"]'),
            (By.CSS_SELECTOR, 'button[aria-label*="Review your application"]'),
            (By.CSS_SELECTOR, 'button[aria-label*="Submit application"]'),
            # 3️⃣ last-resort primary CTA
            (By.CSS_SELECTOR, 'button.artdeco-button--primary'),
        ]

        # the modal scroll-container (same on every step)
        modal = self.driver.find_element(By.CSS_SELECTOR,
                                        'div.jobs-easy-apply-modal__content')

        header = self.driver.find_element(By.TAG_NAME, "h3").text.lower()
        wait_s = 18 if "additional questions" in header else 6

        for by, sel in locators:
            # ① element must exist
            try:
                btn = footer.find_element(by, sel)       # ‹— search *inside* footer
            except NoSuchElementException:
                continue

            # ② bring it into view → required on “Review” page
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", btn
            )

            # ③ wait until it’s actually clickable (enabled & no overlay)
            # Debug button information
            logger.debug(f"Button candidate: {btn.text} | disabled: {btn.get_attribute('disabled')} | "
                        f"aria-disabled: {btn.get_attribute('aria-disabled')} | "
                        f"classes: {btn.get_attribute('class')}")

            try:
                WebDriverWait(self.driver, 6).until(
                    EC.element_to_be_clickable((by, sel))
                )
                return btn                    # success!
            except TimeoutException:
                if btn.is_displayed():
                    logger.debug("Forcing JS click on primary CTA")
                    return btn   
                continue
                # try next locator

        raise TimeoutException("No primary Easy-Apply button found")

    def _next_or_submit(self) -> bool:
        """
        Click the current primary button.

        Returns
        -------
        True   → application fully submitted (Easy-Apply modal closed)
        False  → still inside wizard; more steps to come
        """
        btn = self._get_primary_action_button()
        label = btn.text.strip() or btn.get_attribute("aria-label")
        logger.info(f"[BUTTON] Found button: '{label}' (tag: {btn.tag_name}, enabled: {btn.is_enabled()}, displayed: {btn.is_displayed()})")
        
        if 'submit' in label.lower():
            logger.info("[BUTTON] Detected SUBMIT button - unfollowing company")
            self._unfollow_company()
            
        self._safe_click(btn)
        logger.info(f"[BUTTON] ✅ Clicked button: '{label}'")

        # Wait for either the modal to vanish OR a fresh primary button to render.
        logger.debug("[WAIT] Waiting for button to become stale or new button to appear...")
        try:
            WebDriverWait(self.driver, 8).until(
                EC.any_of(
                    EC.invisibility_of_element(btn),                       # modal closed
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        'button[data-live-test-easy-apply-submit-button],'  # new step
                        'button[data-live-test-easy-apply-review-button],'
                        'button[data-live-test-easy-apply-next-button]'
                    ))
                )
            )
            logger.debug("[WAIT] ✅ Button transition completed")
        except TimeoutException:
            logger.error("[WAIT] ❌ Timeout waiting for button transition - checking for errors")
            self._check_for_errors()
            raise

        # Check if Easy Apply modal still exists (not just any modal - confirmation modal is different)
        try:
            easy_apply_modal = self.driver.find_element(By.CSS_SELECTOR, "div.jobs-easy-apply-modal")
            logger.debug(f"[MODAL CHECK] Easy Apply modal still exists - modal visible: {easy_apply_modal.is_displayed()}")
            return False   # Easy Apply modal still open → more steps
        except NoSuchElementException:
            # Easy Apply modal closed - either fully submitted or showing confirmation modal
            logger.info("[MODAL CHECK] ✅ Easy Apply modal closed - application complete")
            
            # Check what modal is showing now
            try:
                other_modal = self.driver.find_element(By.CSS_SELECTOR, "div.artdeco-modal")
                logger.debug(f"[MODAL CHECK] Found other modal type: {other_modal.get_attribute('class')}")
            except NoSuchElementException:
                logger.debug("[MODAL CHECK] No modal present at all")
                
            return True    # Easy Apply process complete





    def _unfollow_company(self) -> None:
        """Untick ‘Follow Company’ on the review step (if it’s there)."""
        try:
            # checkbox is always visually–hidden; click the label instead
            label = self.driver.find_element(
                By.CSS_SELECTOR,
                "footer label[for='follow-company-checkbox']"
            )
            # scroll so the label is free of the sticky footer
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", label)
            time.sleep(0.2)

            # only click if it is actually checked
            cb = self.driver.find_element(By.ID, "follow-company-checkbox")
            if cb.is_selected():
                self._safe_click(label)      # uses JS click → no interception
        except NoSuchElementException:
            pass            # nothing to unfollow on this job



    def _check_for_errors(self) -> None:
        """
        Raise only if an *active* error message is present
        (LinkedIn keeps the error DIV in the DOM even after the problem is fixed).
        """
        active_errors = [
            e.text.strip() for e in
            self.driver.find_elements(By.CLASS_NAME, "artdeco-inline-feedback--error")
            if e.is_displayed() and e.text.strip()
        ]
        if active_errors:
            # Dump HTML for debugging
            try:
                form = self.driver.find_element(By.TAG_NAME, "form")
                html_content = form.get_attribute("outerHTML")
                
                # Save to debug file
                debug_dir = Path("debug_html")
                debug_dir.mkdir(exist_ok=True)
                
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                debug_file = debug_dir / f"form_error_{timestamp}.html"
                
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                logger.error(f"[FORM ERROR] Validation errors found: {active_errors}")
                logger.error(f"[FORM ERROR] HTML saved to: {debug_file}")
                
                # Also log visible form fields
                try:
                    visible_selects = self.driver.find_elements(By.TAG_NAME, "select")
                    logger.error("[FORM ERROR] Visible dropdowns:")
                    for select in visible_selects:
                        if select.is_displayed():
                            try:
                                label = select.find_element(By.XPATH, "./ancestor::div[@data-test-form-element]//label")
                                label_text = label.text.strip()
                            except:
                                label_text = "Unknown"
                            
                            sel = Select(select)
                            selected = sel.first_selected_option.text
                            logger.error(f"  - {label_text}: '{selected}'")
                except Exception as e:
                    logger.error(f"[FORM ERROR] Could not log dropdown states: {e}")
                    
            except Exception as e:
                logger.error(f"[FORM ERROR] Could not save debug HTML: {e}")
            
            raise Exception(f"Failed answering or file upload. {active_errors}")

    def _discard_application(self) -> None:
        try:
            self.driver.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss').click()
            time.sleep(random.uniform(3, 5))
            self.driver.find_elements(By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn')[0].click()
            time.sleep(random.uniform(3, 5))
        except Exception as e:
            pass

    def fill_up(self) -> None:
        try:
            easy_apply_content = self.driver.find_element(By.CLASS_NAME, 'jobs-easy-apply-content')
            pb4_elements = easy_apply_content.find_elements(By.CLASS_NAME, 'pb4')
            for element in pb4_elements:
                self._process_form_element(element)
        except Exception as e:
            pass

    def _is_upload_field(self, element: WebElement) -> bool:
        try:
            element.find_element(By.XPATH, ".//input[@type='file']")
            return True
        except NoSuchElementException:
            return False




    def _handle_upload_fields(self, block: WebElement) -> bool:
        """
        Upload résumé or cover-letter inside *block*.

        Returns
        -------
        bool
            True  ↦  something was uploaded / selected
            False ↦  nothing done (e.g. we had no local résumé to send)
        """
        def _find_file_input():
            """Helper to re-find file input to avoid stale element issues."""
            try:
                return block.find_element(By.CSS_SELECTOR, "input[type='file']")
            except NoSuchElementException:
                return None

        file_input = _find_file_input()
        if not file_input:
            return False

        # Identify what the block expects
        try:
            input_id = (file_input.get_attribute("id") or "").lower()
        except Exception:
            # If element is stale, re-find it
            file_input = _find_file_input()
            if not file_input:
                return False
            input_id = (file_input.get_attribute("id") or "").lower()

        wants_cover = any(k in input_id for k in ("cover", "motivation"))
        wants_resume = not wants_cover

        # Make the <input> interact-able - re-find element before script execution
        try:
            fresh_input = _find_file_input()
            if fresh_input:
                self.driver.execute_script(
                    "arguments[0].classList.remove('hidden');", fresh_input
                )
        except Exception as e:
            logger.warning(f"Failed to make input interactable: {e}")

        uploaded = False

        # ── résumé ─────────────────────────────────────────────────────────
        if wants_resume and self.resume_dir:
            try:
                fresh_input = _find_file_input()
                if fresh_input:
                    fresh_input.send_keys(str(self.resume_dir.resolve()))
                    uploaded = True
            except Exception as e:
                logger.warning(f"Resume upload failed, retrying: {e}")
                # Retry once with a fresh element
                try:
                    time.sleep(0.5)
                    fresh_input = _find_file_input()
                    if fresh_input:
                        fresh_input.send_keys(str(self.resume_dir.resolve()))
                        uploaded = True
                except Exception as e2:
                    logger.error(f"Resume upload failed after retry: {e2}")

        # ── cover letter (generated on-the-fly) ────────────────────────────
        if wants_cover:
            try:
                fresh_input = _find_file_input()
                if fresh_input:
                    self._create_and_upload_cover_letter(fresh_input)
                    uploaded = True
            except Exception as e:
                logger.warning(f"Cover letter upload failed: {e}")

        if not uploaded:
            return False

        # Tell LinkedIn the field changed so it refreshes footer CTA
        try:
            fresh_input = _find_file_input()
            if fresh_input:
                for evt in ("change", "blur"):
                    try:
                        self.driver.execute_script(
                            "arguments[0].dispatchEvent(new Event(arguments[1],{bubbles:true}));",
                            fresh_input, evt
                        )
                    except Exception as e:
                        logger.warning(f"Failed to dispatch {evt} event: {e}")
        except Exception as e:
            logger.warning(f"Failed to dispatch events on upload field: {e}")

        # tiny guard: press ESC once – closes any stray OS picker if one appeared
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        time.sleep(0.2)

        return True

    def _create_and_upload_resume(self, element: WebElement) -> None:
        """
        Create and upload a dynamically generated resume PDF.
        
        This method is currently disabled as it generates resumes on-the-fly.
        The implementation can be enabled if needed for specific use cases.
        
        Args:
            element: The file input element to upload to
            
        Returns:
            True if resume was successfully created and uploaded
            
        Raises:
            Exception: If maximum retries are reached and upload fails
        """
        max_retries = 3
        retry_delay = 1
        folder_path = 'generated_cv'

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            
        for attempt in range(max_retries):
            try:
                # NOTE: Resume generation is currently disabled
                # Uncomment and implement the following if dynamic resume generation is needed:
                #
                # html_string = self.gpt_answerer.get_resume_html()
                # with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as temp_html_file:
                #     temp_html_file.write(html_string)
                #     file_name_HTML = temp_html_file.name
                #
                # file_name_pdf = f"resume_{uuid.uuid4().hex}.pdf"
                # file_path_pdf = os.path.join(folder_path, file_name_pdf)
                # 
                # with open(file_path_pdf, "wb") as f:
                #     f.write(base64.b64decode(utils.HTML_to_PDF(file_name_HTML)))
                #     
                # element.send_keys(os.path.abspath(file_path_pdf))
                # time.sleep(2)  # Give some time for the upload process
                # os.remove(file_name_HTML)
                
                return True
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    tb_str = traceback.format_exc()
                    raise Exception(f"Max retries reached. Upload failed: \nTraceback:\n{tb_str}")

    def _upload_resume(self, element: WebElement) -> None:
        """
        Upload the configured resume file to the given file input element.
        
        Args:
            element: The file input element to upload the resume to
        """
        element.send_keys(str(self.resume_dir))

    def _create_and_upload_cover_letter(self, element: WebElement) -> None:
        """
        Generate and upload a cover letter PDF using AI.
        
        Creates a temporary PDF file containing an AI-generated cover letter
        and uploads it to the specified file input element.
        
        Args:
            element: The file input element to upload the cover letter to
        """
        cover_letter = self.gpt_answerer.answer_question_textual_wide_range("Write a cover letter")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf_file:
            letter_path = temp_pdf_file.name
            c = canvas.Canvas(letter_path, pagesize=letter)
            width, height = letter
            text_object = c.beginText(100, height - 100)
            text_object.setFont("Helvetica", 12)
            text_object.textLines(cover_letter)
            c.drawText(text_object)
            c.save()
            element.send_keys(letter_path)

    def _fill_additional_questions(self) -> None:
        """
        Process additional questions in the Easy Apply form.
        
        Finds and processes form sections that contain additional questions
        beyond the basic application information.
        """
        form_sections = self.driver.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-section__grouping')
        for section in form_sections:
            self._process_question(section)

    def _process_question(self, section: WebElement) -> None:
        """
        Process a single question section in the application form.
        
        Delegates to specific handlers based on the type of form element found.
        
        Args:
            section: WebElement containing the question to process
        """
        if self._handle_terms_of_service(section):
            return
        self._handle_radio_question(section)
        self._handle_textbox_question(section)
        self._handle_date_question(section)
        self._handle_dropdown_question(section)

    def _handle_terms_of_service(self, element: WebElement) -> bool:
        """
        Handle terms of service, privacy policy, and similar checkboxes.
        
        Automatically accepts terms and conditions checkboxes by detecting
        common keywords in multiple languages.
        
        Args:
            element: WebElement containing the checkbox
            
        Returns:
            True if a terms checkbox was found and clicked, False otherwise
        """
        try:
            checkbox = element.find_element(By.TAG_NAME, 'label')
            question_text = checkbox.text.lower()
            if any(kw in question_text for kw in (
                    'terms of service', 'privacy policy', 'terms of use',
                    'politique de confidentialité', 'conditions d’utilisation',
                    'j\'accepte', 'confidentialité')):
                checkbox.click()
                return True
            return False
        except NoSuchElementException:
            return False

    def _handle_radio_question(self, element: WebElement) -> bool:
        """
        Answer LinkedIn radio-group questions, reusing saved answers whenever
        possible, otherwise asking GPT and persisting the result.
        """
        try:
            if not element.find_elements(By.CSS_SELECTOR, "input[type=radio]"):
                return False

            try:
                legend = element.find_element(By.TAG_NAME, "legend")
                question_text = legend.text.strip()
            except NoSuchElementException:
                title = element.find_element(
                    By.CSS_SELECTOR,
                    "[data-test-text-entity-list-form-title], "
                    ".fb-dash-form-element__label-title--is-required",
                )
                question_text = title.text.strip()

            labels  = element.find_elements(By.TAG_NAME, "label")
            if not labels:
                return False

            if element.find_elements(By.CSS_SELECTOR, "input[type=radio]:checked"):
                return True  # already answered

            options = [lbl.text.strip() for lbl in labels if lbl.text.strip()]
            key     = question_text.lower()

            answer  = next(
                (ans for substr, ans in self.answers.items() if substr in key and ans in options),
                None,
            )

            generated = False
            if not answer:
                answer     = self.gpt_answerer.answer_question_from_options(question_text, options).strip()
                generated  = True

            logger.debug(f"RADIO Q: {question_text!r} → chosen: {answer!r}")

            for lbl in labels:
                if lbl.text.strip().lower() == answer.lower():
                    self._safe_click(lbl)
                    break
            else:  # fallback
                self._safe_click(labels[0])

            if generated:
                self._remember_answer("radio", question_text, answer)

            time.sleep(0.3)
            return True

        except NoSuchElementException:
            return False


    def _clamp_numeric_answer(self, raw_answer, min_val=None, max_val=None):
        """
        Clamp numeric answer to given range. If no range provided, return as-is.
        
        Args:
            raw_answer: The numeric answer to clamp
            min_val: Minimum allowed value (optional)
            max_val: Maximum allowed value (optional)
            
        Returns:
            String representation of the clamped value
        """
        try:
            if isinstance(raw_answer, (int, float)):
                intval = int(raw_answer)
            else:
                intval = int(float(str(raw_answer).strip()))
        except Exception:
            # If we can't parse the number, return 1 as a safe fallback
            return "1"
        
        # Only clamp if bounds are provided
        if min_val is not None:
            intval = max(min_val, intval)
        if max_val is not None:
            intval = min(max_val, intval)
            
        return str(intval)

    def _get_numeric_range_from_gpt(self, question_text: str, error_text: str) -> tuple[int, int]:
        """
        Ask GPT to determine appropriate min/max values for a numeric question based on error context.
        
        Args:
            question_text: The original question
            error_text: The validation error message
            
        Returns:
            Tuple of (min_val, max_val) for the question
        """
        try:
            range_response = self.gpt_answerer.get_numeric_range(question_text, error_text)
            # Parse response like "1,99" or "0,10" 
            min_val, max_val = map(int, range_response.split(','))
            return min_val, max_val
        except Exception as e:
            logger.warning(f"Failed to get numeric range from GPT: {e}")
            # Fallback to conservative range
            return 1, 99

    def _handle_multiline_question(self, element: WebElement) -> bool:
        try:
            element.find_element(By.CSS_SELECTOR,
                                 "[data-test-multiline-text-form-component]")
            question_text = element.find_element(By.TAG_NAME, "label").text.strip()
            textarea      = element.find_element(By.TAG_NAME, "textarea")

            answer = (self.gpt_answerer
                      .answer_question_textual_wide_range(question_text) or "").strip()
            if not answer:
                return False

            textarea.clear()
            textarea.send_keys(answer)
            time.sleep(0.5)
            return True

        except NoSuchElementException:
            return False
        except Exception as exc:
            logger.error(f"MULTILINE exception: {exc}")
            return False

    def _handle_typeahead_field(self, element: WebElement, text_field: WebElement, question_text: str) -> bool:
        """
        Handle typeahead/autocomplete fields (e.g., city, company name).
        
        These fields require:
        1. Type text
        2. Wait for dropdown suggestions
        3. Click a suggestion from the list
        
        Args:
            element: The form element container
            text_field: The input field
            question_text: The question text
            
        Returns:
            True if handled successfully
        """
        logger.info(f"[TYPEAHEAD] Handling typeahead field: {question_text!r}")
        
        # Skip if already filled
        if text_field.get_attribute("value").strip():
            logger.debug("[TYPEAHEAD] Field already has value, skipping")
            text_field.send_keys(Keys.TAB)
            time.sleep(0.3)
            return True
        
        # Get answer from GPT
        try:
            answer = self.gpt_answerer.answer_question_textual_wide_range(question_text)
            if not answer or not answer.strip():
                logger.warning("[TYPEAHEAD] No answer from GPT, using N/A")
                answer = "N/A"
            
            logger.debug(f"[TYPEAHEAD] Typing: {answer!r}")
            
            # Clear field and type answer
            text_field.clear()
            text_field.send_keys(answer)
            time.sleep(1.5)  # Wait for dropdown to appear
            
            # Look for dropdown suggestions
            try:
                # LinkedIn uses different dropdown structures
                dropdown_selectors = [
                    # Modern typeahead dropdown
                    (By.CSS_SELECTOR, "div.basic-typeahead__selectable"),
                    # Alternative selector
                    (By.CSS_SELECTOR, "div[role='option']"),
                    # Legacy dropdown
                    (By.CSS_SELECTOR, "li.typeahead__result-item"),
                ]
                
                suggestions = []
                for by, selector in dropdown_selectors:
                    try:
                        suggestions = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_all_elements_located((by, selector))
                        )
                        if suggestions:
                            logger.debug(f"[TYPEAHEAD] Found {len(suggestions)} suggestions using {selector}")
                            break
                    except TimeoutException:
                        continue
                
                if not suggestions:
                    logger.warning("[TYPEAHEAD] No dropdown suggestions appeared")
                    # Try pressing Enter or Tab
                    text_field.send_keys(Keys.TAB)
                    time.sleep(0.5)
                    return True
                
                # Click first visible suggestion
                clicked = False
                for suggestion in suggestions:
                    try:
                        if not suggestion.is_displayed():
                            continue
                            
                        suggestion_text = suggestion.text[:50]  # Get text before clicking
                        logger.info(f"[TYPEAHEAD] ✅ Clicking suggestion: {suggestion_text}")
                        
                        # Try ActionChains for more reliable click
                        from selenium.webdriver.common.action_chains import ActionChains
                        actions = ActionChains(self.driver)
                        actions.move_to_element(suggestion).click().perform()
                        
                        clicked = True
                        logger.debug(f"[TYPEAHEAD] Click completed, waiting for value to register...")
                        time.sleep(1.0)  # Wait for selection to register
                        break  # Exit loop after successful click
                        
                    except Exception as click_error:
                        error_str = str(click_error).lower()
                        # Stale element after click is OK - it means the dropdown closed
                        if "stale element" in error_str:
                            logger.debug(f"[TYPEAHEAD] Element became stale after click (dropdown closed - this is OK)")
                            clicked = True
                            break
                        logger.warning(f"[TYPEAHEAD] Error clicking suggestion: {click_error}")
                        continue
                
                if clicked:
                    logger.debug("[TYPEAHEAD] Selection completed, verifying...")
                    # Give LinkedIn time to update the form
                    time.sleep(0.5)
                    
                    # Try to verify the value was set (best effort)
                    try:
                        current_value = text_field.get_attribute("value") or ""
                        if current_value.strip():
                            logger.info(f"[TYPEAHEAD] ✅ Field value set to: {current_value[:30]}")
                        else:
                            logger.warning(f"[TYPEAHEAD] Field appears empty after click, but continuing...")
                    except:
                        # Field might be stale, which is OK
                        logger.debug("[TYPEAHEAD] Could not verify field value (field may be stale)")
                    
                    return True
                
                logger.warning("[TYPEAHEAD] No visible suggestions found, pressing Tab")
                try:
                    text_field.send_keys(Keys.TAB)
                except:
                    pass  # Field might be stale
                time.sleep(0.5)
                return True
                
            except Exception as e:
                # Stale element after successful click is OK
                if "stale element" in str(e).lower():
                    logger.debug(f"[TYPEAHEAD] Element became stale (dropdown closed after selection)")
                    return True
                logger.error(f"[TYPEAHEAD] Error finding dropdown: {e}")
                # Try to move on - the field might be filled
                try:
                    text_field.send_keys(Keys.TAB)
                except:
                    pass  # Field might be gone
                time.sleep(0.5)
                return True
                
        except Exception as e:
            logger.error(f"[TYPEAHEAD] Error handling typeahead field: {e}")
            return False


    # ---------------------------------------------------------------------------
    # REPLACE the whole _handle_textbox_question
    # ---------------------------------------------------------------------------
    def _handle_textbox_question(self, element: WebElement) -> bool:
        """Answer single-line text or numeric inputs and remember GPT answers."""
        if not (element.find_elements(By.TAG_NAME, "input") or element.find_elements(By.TAG_NAME, "textarea")):
            return False

        try:
            question_text = self._deep_label_text(element).lower()
        except NoSuchElementException:
            return False

        # locate the visible input
        text_field = None
        for inp in element.find_elements(By.TAG_NAME, "input"):
            if inp.is_displayed() and (inp.get_attribute("type") or "").lower() not in ("hidden", "file"):
                text_field = inp
                break
        if text_field is None:
            for ta in element.find_elements(By.TAG_NAME, "textarea"):
                if ta.is_displayed():
                    text_field = ta
                    break
        if text_field is None:
            return False

        # Check if this is a typeahead/autocomplete field
        role = text_field.get_attribute("role") or ""
        aria_autocomplete = text_field.get_attribute("aria-autocomplete") or ""
        
        if role == "combobox" and aria_autocomplete == "list":
            logger.debug(f"[TYPEAHEAD] Detected typeahead field: {question_text!r}")
            return self._handle_typeahead_field(element, text_field, question_text)

        if text_field.get_attribute("value").strip():
            text_field.send_keys(Keys.TAB)
            time.sleep(0.3)
            return True

        field_id   = text_field.get_attribute("id") or ""
        is_numeric = "-numeric" in field_id

        answer = self._get_answer_from_set("numeric" if is_numeric else "text", question_text)
        generated = False

        if not answer:
            generated = True
            # Use GPT answerer for all questions instead of hardcoded values
            raw = (
                self.gpt_answerer.answer_question_numeric(question_text)
                if is_numeric
                else self.gpt_answerer.answer_question_textual_wide_range(question_text)
            )
            # Ensure answer is always a string
            answer = str(raw) if raw is not None else ""

        # Don't clamp by default - let the original answer through first
        if not answer.strip():
            answer = "0" if is_numeric else "N/A"

        logger.debug(f"TEXTBOX Q: {question_text!r} → {answer!r}")
        
        # Try to enter the answer
        self._enter_answer_with_retry(text_field, answer, question_text, is_numeric, generated)

        return True

    def _enter_answer_with_retry(self, text_field: WebElement, answer: str, question_text: str, is_numeric: bool, generated: bool):
        """
        Enter answer into text field with intelligent retry on validation errors.
        
        If validation fails, asks GPT for appropriate numeric ranges and retries with clamped value.
        """
        max_retries = 2
        
        for attempt in range(max_retries + 1):
            try:
                text_field.clear()
                text_field.send_keys(answer)
                text_field.send_keys(Keys.TAB)
                time.sleep(0.5)
                
                # Check for validation errors
                error_elements = self.driver.find_elements(By.CSS_SELECTOR, ".artdeco-inline-feedback--error")
                active_errors = [e for e in error_elements if e.is_displayed() and e.text.strip()]
                
                if not active_errors:
                    # Success! Remember the answer if it was generated
                    if generated:
                        self._remember_answer("numeric" if is_numeric else "text", question_text, answer)
                    return
                    
                # We have validation errors - handle them
                if attempt < max_retries and is_numeric:
                    error_text = " ".join([e.text.strip() for e in active_errors])
                    logger.debug(f"Validation error for {question_text}: {error_text}")
                    
                    # Ask GPT for appropriate range
                    min_val, max_val = self._get_numeric_range_from_gpt(question_text, error_text)
                    logger.debug(f"GPT suggested range: {min_val}-{max_val}")
                    
                    # Re-clamp the answer with the suggested range
                    original_answer = answer
                    answer = self._clamp_numeric_answer(answer, min_val, max_val)
                    logger.debug(f"Clamped {original_answer} to {answer} using range {min_val}-{max_val}")
                    
                    continue  # Retry with clamped value
                else:
                    # Final attempt failed or not numeric - log and continue
                    logger.warning(f"Failed to resolve validation error for {question_text}: {[e.text for e in active_errors]}")
                    break
                    
            except Exception as e:
                logger.error(f"Error entering answer attempt {attempt + 1}: {e}")
                if attempt == max_retries:
                    break
                time.sleep(0.5)

        return True



    def _handle_date_question(self, element: WebElement) -> bool:
        """
        Handle date picker form elements.
        
        Automatically fills date picker inputs with today's date if they are empty.
        
        Args:
            element: WebElement containing the date picker
            
        Returns:
            True if a date was filled, False if not a date picker or already filled
        """
        try:
            date_picker = element.find_element(By.CLASS_NAME, 'artdeco-datepicker__input')
            if date_picker.get_attribute('value').strip():
                return False

            date_picker.clear()
            date_picker.send_keys(date.today().strftime("%m/%d/%y"))
            date_picker.send_keys(Keys.RETURN)
            time.sleep(0.3)
            return True

        except NoSuchElementException:
            return False
        except Exception as e:
            logger.error(f"Date question handling error: {e}")
            return False

    def _handle_dropdown_question(self, element: WebElement) -> bool:
        """
        Handle dropdown (select) form elements.
        
        Detects dropdown questions, checks if already answered, and selects
        appropriate options using saved answers or AI-generated responses.
        
        Args:
            element: WebElement containing the dropdown
            
        Returns:
            True if a dropdown option was selected, False if not a dropdown or already answered
        """
        try:
            question_text = element.find_element(By.TAG_NAME, "label").text.lower()
            dropdown      = element.find_element(By.TAG_NAME, "select")
            select        = Select(dropdown)

            logger.info(f"[DROPDOWN] Processing question: {question_text!r}")
            
            first = select.first_selected_option.text.strip().lower()
            logger.debug(f"[DROPDOWN] Currently selected: {first!r}")
            
            if first and not any(tok in first for tok in ("select", "sélect", "selecciona", "choose", "choisissez")) \
            and not dropdown.is_enabled():
                logger.debug(f"[DROPDOWN] Already answered and disabled, skipping")
                return False  # already confirmed

            options   = [o.text for o in select.options]
            logger.debug(f"[DROPDOWN] Available options ({len(options)}): {options[:5]}{'...' if len(options) > 5 else ''}")
            
            # First try: exact match from saved answers
            logger.debug(f"[DROPDOWN] Try 1: Checking saved answers")
            answer    = self._get_answer_from_set("dropdown", question_text, options)
            generated = False
            
            if answer:
                logger.info(f"[DROPDOWN] ✅ Found saved answer: {answer!r}")
            
            # Second try: smart matching for common fields (phone country, email, etc.)
            if not answer:
                logger.debug(f"[DROPDOWN] Try 2: Attempting smart match")
                answer = self._smart_dropdown_match(question_text, options)
                if answer:
                    logger.info(f"[DROPDOWN] ✅ Smart match found: {answer!r}")
            
            # Third try: Ask GPT
            if not answer:
                logger.debug(f"[DROPDOWN] Try 3: Asking GPT")
                try:
                    answer = self.gpt_answerer.answer_question_from_options(question_text, options)
                    generated = True
                    logger.info(f"[DROPDOWN] ✅ GPT answered: {answer!r}")
                except Exception as e:
                    logger.warning(f"[DROPDOWN] GPT failed: {e}")
                    answer = None
            
            # Last resort: select first non-placeholder option
            if not answer:
                logger.warning(f"[DROPDOWN] Try 4: Using fallback (first non-placeholder)")
                placeholder = ("select", "sélect", "selecciona", "choose", "choisissez", "opción")
                answer = next((o for o in options if not any(p in o.lower() for p in placeholder)),
                            options[1] if len(options) > 1 else options[0])
                generated = True
                logger.warning(f"[DROPDOWN] ⚠️ Fallback selection: {answer!r}")

            logger.info(f"[DROPDOWN] Final answer: {question_text!r} → {answer!r}")
            self._select_dropdown(dropdown, answer)

            for evt in ("change", "blur"):
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event(arguments[1],{bubbles:true}));",
                    dropdown, evt,
                )

            if generated:
                self._remember_answer("dropdown", question_text, answer)

            return True

        except NoSuchElementException:
            return False


    def _find_text_field(self, question: WebElement) -> WebElement:
        """
        Find the text input field within a question element.
        
        Tries to locate an input element first, falling back to textarea.
        
        Args:
            question: WebElement containing the form question
            
        Returns:
            The text input or textarea element
            
        Raises:
            NoSuchElementException: If no text field is found
        """
        try:
            return question.find_element(By.TAG_NAME, 'input')
        except NoSuchElementException:
            return question.find_element(By.TAG_NAME, 'textarea')

    def _is_numeric_field(self, field: WebElement) -> bool:
        """
        Determine if a field expects numeric input.
        
        Checks the field's type attribute and ID for numeric indicators.
        
        Args:
            field: The input field to check
            
        Returns:
            True if the field expects numeric input, False otherwise
        """
        field_type = field.get_attribute('type').lower()
        if 'numeric' in field_type:
            return True
        class_attribute = field.get_attribute("id")
        return class_attribute and 'numeric' in class_attribute

    def _enter_text(self, element: WebElement, text: str) -> None:
        """
        Enter text into a form field with autocomplete handling.
        
        Clears the field, enters the text, and handles any autocomplete
        dropdowns that may appear.
        
        Args:
            element: The form field to enter text into
            text: The text to enter
        """
        element.clear()
        element.send_keys(text)
        time.sleep(0.5)  # Allow the dropdown to appear, if any

        # Check for any dropdowns or autocomplete suggestions
        try:
            # Locate the first dropdown suggestion and click it
            dropdown = WebDriverWait(self.driver, 2).until(
                EC.visibility_of_element_located((By.CLASS_NAME, 'search-typeahead-v2__hit'))
            )
            dropdown.click()
            time.sleep(0.5)  # Wait to ensure the selection is made
        except (NoSuchElementException, TimeoutException):
            pass  # If no dropdown, continue as normal


    def _select_dropdown(self, element: WebElement, text: str) -> None:
        """
        Select an option from a dropdown element with intelligent matching.
        
        Uses multiple strategies to find the best match:
        1. Exact text match
        2. Case-insensitive substring match
        3. Fallback to first non-placeholder option
        
        Args:
            element: The select dropdown element
            text: The text to search for in options
        """
        select = Select(element)

        # ⓐ exact
        try:
            select.select_by_visible_text(text)
            return
        except Exception:
            pass

        # ⓑ case-insensitive substring match
        for opt in select.options:
            if text.lower() in opt.text.lower():
                select.select_by_visible_text(opt.text)
                return

        # ⓒ sane fallback (skip “Select an option” / “Choose …”)
        for opt in select.options:
            t = opt.text.strip().lower()
            if t and not any(tok in t for tok in ("select", "sélect", "choose", "choisissez")):
                select.select_by_visible_text(opt.text)
                return


    def _select_radio(self, radios: List[WebElement], answer: str) -> None:
        """
        Select a radio button option based on text matching.
        
        Searches through radio button options for a match with the answer text.
        Falls back to the last option if no match is found.
        
        Args:
            radios: List of radio button elements
            answer: The answer text to match against
        """
        for radio in radios:
            if answer in radio.text.lower():
                radio.find_element(By.TAG_NAME, 'label').click()
                return
        radios[-1].find_element(By.TAG_NAME, 'label').click()

    def _handle_form_errors(self, element: WebElement, question_text: str, answer: str, text_field: WebElement) -> None:
        """
        Handle form validation errors by asking AI to fix the answer.
        
        Detects inline error messages and uses AI to generate a corrected response.
        
        Args:
            element: The form element containing the error
            question_text: The original question text
            answer: The answer that caused the error
            text_field: The text field to update with the corrected answer
        """
        try:
            error = element.find_element(By.CLASS_NAME, 'artdeco-inline-feedback--error')
            error_text = error.text.lower()
            new_answer = self.gpt_answerer.try_fix_answer(question_text, answer, error_text)
            self._enter_text(text_field, new_answer)
        except NoSuchElementException:
            pass

    def _generate_tailored_resume(self, job: Any, job_description: str) -> str:
        """
        Generate a tailored resume for the specific job application.
        
        Args:
            job: Job object containing job details
            job_description: Full job description text
            
        Returns:
            Path to the generated tailored resume PDF
        """
        try:
            # Get base config path
            base_config_path = Path(__file__).parent / "resumy" / "myconfig.yaml"
            
            if not base_config_path.exists():
                logger.warning(f"Base config not found: {base_config_path}")
                return str(self.resume_dir) if self.resume_dir else ""
            
            logger.info(f"🎯 Tailoring resume for {job.company} - {job.title}")
            
            # Use GPT to tailor the resume configuration
            tailored_config = self.gpt_answerer.tailor_resume_to_job(
                job_description, str(base_config_path)
            )
            
            # Validate the tailored configuration
            if not resume_generator.validate_yaml_config(tailored_config):
                logger.warning("Invalid tailored config, using original resume")
                return str(self.resume_dir) if self.resume_dir else ""
            
            # Generate the tailored PDF
            tailored_pdf_path = resume_generator.generate_tailored_resume(
                company_name=job.company,
                job_title=job.title,
                tailored_config_yaml=tailored_config
            )
            
            logger.info(f"✅ Tailored resume generated: {tailored_pdf_path}")
            
            # Clean up old resumes periodically
            resume_generator.cleanup_old_resumes()
            
            return tailored_pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate tailored resume: {e}")
            # Fallback to original resume if available
            if self.resume_dir and self.resume_dir.exists():
                logger.info("Using fallback resume")
                return str(self.resume_dir)
            else:
                logger.warning("No fallback resume available")
                return ""
