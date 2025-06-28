import csv
import os
import random
import time
import traceback
from itertools import product
from pathlib import Path
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import utils
from job import Job
from linkedIn_easy_applier import LinkedInEasyApplier
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC


class EnvironmentKeys:
    def __init__(self):
        self.skip_apply = self._read_env_key_bool("SKIP_APPLY")
        self.disable_description_filter = self._read_env_key_bool("DISABLE_DESCRIPTION_FILTER")

    @staticmethod
    def _read_env_key(key: str) -> str:
        return os.getenv(key, "")

    @staticmethod
    def _read_env_key_bool(key: str) -> bool:
        return os.getenv(key) == "True"

class LinkedInJobManager:
    def __init__(self, driver):
        self.driver = driver
        self.set_old_answers: dict[tuple[str, str], str] = {}  # (type, substr) ➜ answer
        self.easy_applier_component = None

    def set_parameters(self, parameters):
        self.company_blacklist = parameters.get('companyBlacklist', []) or []
        self.title_blacklist = parameters.get('titleBlacklist', []) or []
        self.positions = parameters.get('positions', [])
        self.locations = parameters.get('locations', [])
        self.base_search_url = self.get_base_search_url(parameters)
        self.seen_jobs = []
        resume_path = parameters.get('uploads', {}).get('resume', None)
        if resume_path is not None and Path(resume_path).exists():
            self.resume_dir = Path(resume_path)
        else:
            self.resume_dir = None
        self.output_file_directory = Path(parameters['outputFileDirectory'])
        self.env_config = EnvironmentKeys()
        self.old_question()  

    def set_gpt_answerer(self, gpt_answerer):
        self.gpt_answerer = gpt_answerer

    def old_question(self):
        """
        Load old answers from a CSV file into a dictionary.
        """
        self.set_old_answers = {}
        file_path = 'data_folder/output/old_Questions.csv'
        if os.path.exists(file_path):
            with open(file_path, 'r', newline='', encoding='utf-8', errors='ignore') as file:
                csv_reader = csv.reader(file, delimiter=',', quotechar='"')
                for row in csv_reader:
                    if len(row) == 3:
                        answer_type, question_text, answer = row
                        self.set_old_answers[(answer_type.lower(), question_text.lower())] = answer




    # ---------------------------------------------------------------------------
    # replace the whole method
    # ---------------------------------------------------------------------------
    def start_applying(self):
        """
        Boot the Easy-Apply helper and iterate through every (position, location)
        search combination – one LinkedIn result page at a time.
        Every brand-new GPT answer that gets generated during a job application
        is persisted through `record_gpt_answer`, so that future runs can reuse it.
        """

        old_answers_as_triples = [
            (q_type, q_sub, ans)              # (str, str, str)
            for (q_type, q_sub), ans in self.set_old_answers.items()
        ]
        # ----

        # hand the persistence callback to the applier  ↓↓↓
        self.easy_applier_component = LinkedInEasyApplier(
            driver            = self.driver,
            resume_dir        = self.resume_dir,
            set_old_answers   = old_answers_as_triples,
            gpt_answerer      = self.gpt_answerer,
            record_answer_cb  = self.record_gpt_answer,   #  ← NEW
        )

        searches           = list(product(self.positions, self.locations))
        random.shuffle(searches)

        page_sleep         = 0
        minimum_time       = 9          # three LinkedIn seconds “feel” safer
        minimum_page_time  = time.time() + minimum_time

        for position, location in searches:
            location_url    = f"&location={location}"
            job_page_number = -1
            utils.printyellow(f"Starting the search for {position} in {location}.")

            try:
                while True:
                    page_sleep      += 1
                    job_page_number += 1

                    utils.printyellow(f"Going to job page {job_page_number}")
                    self.next_job_page(position, location_url, job_page_number)
                    time.sleep(random.uniform(0.2, 1.0))

                    utils.printyellow("Starting the application process for this page…")
                    self.apply_jobs()
                    utils.printyellow("Applications on this page completed ✔")

                    # stay human-like – minimum dwell time
                    time_left = minimum_page_time - time.time()
                    if time_left > 0:
                        time.sleep(time_left)
                    minimum_page_time = time.time() + minimum_time

                    # sprinkle occasional long pauses
                    if page_sleep % 5 == 0:
                        page_sleep += 1
            except Exception:
                utils.printred(f"Error on page {job_page_number}:\n{traceback.format_exc()}")
                break



    # def start_applying(self):
    #     self.easy_applier_component = LinkedInEasyApplier(
    #         self.driver, self.resume_dir, self.set_old_answers, self.gpt_answerer
    #     )

    #     searches = list(product(self.positions, self.locations))
    #     random.shuffle(searches)
    #     page_sleep = 0
    #     minimum_time = 3 * 3
    #     minimum_page_time = time.time() + minimum_time

    #     for position, location in searches:
    #         location_url = "&location=" + location
    #         job_page_number = -1
    #         utils.printyellow(f"Starting the search for {position} in {location}.")

    #         try:
    #             while True:
    #                 page_sleep += 1
    #                 job_page_number += 1
    #                 utils.printyellow(f"Going to job page {job_page_number}")
    #                 self.next_job_page(position, location_url, job_page_number)
    #                 time.sleep(random.uniform(0.2, 1))
    #                 utils.printyellow("Starting the application process for this page...")
    #                 self.apply_jobs()
    #                 utils.printyellow("Applying to jobs on this page has been completed!")

    #                 time_left = minimum_page_time - time.time()
    #                 if time_left > 0:
    #                     # utils.printyellow(f"Sleeping for {time_left} seconds.")
    #                     # time.sleep(time_left)
    #                     minimum_page_time = time.time() + minimum_time
    #                 if page_sleep % 5 == 0:
    #                     # sleep_time = random.randint(5, 34)
    #                     # utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
    #                     # time.sleep(sleep_time)
    #                     page_sleep += 1
    #         except Exception:
    #             utils.printred(f"Error on page {job_page_number}:\n{traceback.format_exc()}")
    #             break
    #         time_left = minimum_page_time - time.time()
    #         if time_left > 0:
    #             # utils.printyellow(f"Sleeping for {time_left} seconds.")
    #             # time.sleep(time_left)
    #             minimum_page_time = time.time() + minimum_time
    #         if page_sleep % 5 == 0:
    #             # sleep_time = random.randint(50, 90)
    #             # utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
    #             # time.sleep(sleep_time)
    #             page_sleep += 1

    def apply_jobs(self):
        try:
            print("first try entered")
            try:
                no_jobs_elements = self.driver.find_elements(By.CLASS_NAME, 'artdeco-empty-state__headline')
                no_jobs_text_found = False
                for el in no_jobs_elements:
                    if 'no results found' in el.text.lower():
                        print("No jobs found")
                        no_jobs_text_found = True
                        break

                if no_jobs_text_found:
                    raise Exception("No more jobs on this page")
            except NoSuchElementException as e:
                print(f"NoSuchElementException: {e}")
                pass
            
            print("fetching job results")

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "li[data-occludable-job-id]")
                    )
                )
            except TimeoutException:
                print("⚠️ No job tiles showed up in 10s. Here's a page snippet:")
                snippet = self.driver.page_source[:500].replace("\n", "")
                print(snippet)
                raise
            
            job_list_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "li[data-occludable-job-id]"
            )

            print(f"Found {len(job_list_elements)} job tiles")
            if not job_list_elements:
                raise Exception("No job tiles found on page")

            for tile in job_list_elements:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tile)
            
            job_list = [
                Job(*self.extract_job_information_from_tile(tile))
                for tile in job_list_elements
            ]

            print(job_list)

            for job in job_list:
                if self.is_blacklisted(job.title, job.company, job.link):
                    utils.printyellow(f"Blacklisted {job.title} at {job.company}, skipping...")
                    self.write_to_file(job.company, job.location, job.title, job.link, "skipped")
                    continue

                try:
                    if job.apply_method not in {"Continue", "Applied", "Apply"}:
                        self.easy_applier_component.job_apply(job)
                except Exception:
                    self.write_to_file(job.company, job.location, job.title, job.link, "failed")
                    utils.printred("apply_jobs failed:\n" + traceback.format_exc())
                    continue
                self.write_to_file(job.company, job.location, job.title, job.link, "success")
                self.seen_jobs.append(job.link)
        
        except Exception as e:
            raise e
    
    def write_to_file(self, company, job_location, job_title, link, file_name):
        to_write = [company, job_title, link, job_location]
        file_path = self.output_file_directory / f"{file_name}.csv"
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(to_write)


    # ---------------------------------------------------------------------------
    # REPLACE the existing method – we now append to old_Questions.csv directly
    # ---------------------------------------------------------------------------
    def record_gpt_answer(self, answer_type: str, question_text: str, gpt_response: str) -> None:
        """
        Persist every never-seen-before Q/A tuple so that `old_question()` can
        preload it next time.
        """
        csv_path = Path("data_folder/output/old_Questions.csv")
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        # De-dup: skip if we already stored exactly the same (type, question) row
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8", newline="") as fh:
                for a_type, q_text, _ in csv.reader(fh):
                    if a_type.lower() == answer_type.lower() and q_text.lower() == question_text.lower():
                        return

        with csv_path.open("a", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerow([answer_type, question_text, gpt_response])


    # def record_gpt_answer(self, answer_type, question_text, gpt_response):
    #     to_write = [answer_type, question_text, gpt_response]
    #     file_path = self.output_file_directory / "registered_jobs.csv"
    #     try:
    #         with open(file_path, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(to_write)
    #     except Exception as e:
    #         utils.printred(f"Error writing registered job: {e}")
    #         utils.printred(f"Details: Answer type: {answer_type}, Question: {question_text}")

    def get_base_search_url(self, parameters):
        url_parts = []
        if parameters['remote']:
            url_parts.append("f_CF=f_WRA")
        experience_levels = [str(i+1) for i, v in enumerate(parameters.get('experienceLevel', [])) if v]
        if experience_levels:
            url_parts.append(f"f_E={','.join(experience_levels)}")
        url_parts.append(f"distance={parameters['distance']}")
        job_types = [key[0].upper() for key, value in parameters.get('jobTypes', {}).items() if value]
        if job_types:
            url_parts.append(f"f_JT={','.join(job_types)}")
        date_mapping = {
            "all time": "",
            "month": "&f_TPR=r2592000",
            "week": "&f_TPR=r604800",
            "24 hours": "&f_TPR=r86400"
        }
        date_param = next((v for k, v in date_mapping.items() if parameters.get('date', {}).get(k)), "")
        url_parts.append("f_LF=f_AL")  # Easy Apply
        base_url = "&".join(url_parts)
        return f"?{base_url}{date_param}"
    
    def next_job_page(self, position, location, job_page):
        self.driver.get(f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}{location}&start={job_page * 25}")
    
    def extract_job_information_from_tile(self, tile):
        # defaults
        title = company = location = link = apply_method = ""

        # 1) Title & link
        try:
            a_tag = tile.find_element(
                By.CSS_SELECTOR, "a.job-card-container__link"
            )
            title = a_tag.text.strip()
            # clean url
            link = a_tag.get_attribute("href").split("?")[0]
        except Exception:
            utils.printred(
                f"[extract] title/link failed:\n{traceback.format_exc()}"
            )

        # 2) Company
        try:
            company = tile.find_element(
                By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle span"
            ).text.strip()
        except Exception:
            utils.printred(
                f"[extract] company failed:\n{traceback.format_exc()}"
            )

        # 3) Location
        try:
            location = tile.find_element(
                By.CSS_SELECTOR,
                "ul.job-card-container__metadata-wrapper li span"
            ).text.strip()
        except Exception:
            utils.printred(
                f"[extract] location failed:\n{traceback.format_exc()}"
            )

        # 4) Apply method (e.g. “Easy Apply” or “Apply on company site”)
        try:
            # last footer <li> often contains the apply method
            footer_lis = tile.find_elements(
                By.CSS_SELECTOR,
                "ul.job-card-list__footer-wrapper li"
            )
            # pick the one whose text isn’t a timestamp or “Viewed”/“Promoted”
            for li in footer_lis:
                text = li.text.strip()
                if text and not any(
                    kw in text.lower() for kw in ("ago", "viewed", "promoted")
                ):
                    apply_method = text
                    break
        except Exception:
            # default to “Applied” so you skip it
            apply_method = "Applied"

        return title, company, location, link, apply_method

    
    def is_blacklisted(self, job_title, company, link):
        job_title_words = job_title.lower().split(' ')
        title_blacklisted = any(word in job_title_words for word in self.title_blacklist)
        company_blacklisted = company.strip().lower() in (word.strip().lower() for word in self.company_blacklist)
        link_seen = link in self.seen_jobs
        return title_blacklisted or company_blacklisted or link_seen