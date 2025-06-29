"""
GPT/LLM Integration for LinkedIn Auto Apply Bot

This module provides AI-powered response generation for LinkedIn Easy Apply forms.
It integrates with OpenAI's GPT models to intelligently answer various types of
application questions including textual responses, multiple choice, and numeric inputs.

Key Features:
- Automatic question categorization and response generation
- Resume-based contextual answers
- Job description analysis and integration
- API call logging and cost tracking
- Template-based response generation for different question types

Classes:
    LLMLogger: Logs all API calls with usage metrics and costs
    LoggerChatModel: Wrapper for ChatOpenAI with logging capabilities
    GPTAnswerer: Main class for generating form responses using AI

Dependencies:
    - OpenAI API via LangChain
    - Custom prompt templates for different question types
    - Resume and job description data for context
"""

import json
import os
import re
import textwrap
from datetime import datetime
from typing import Dict, List

from dotenv import load_dotenv
from langchain_core.messages.ai import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompt_values import StringPromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from Levenshtein import distance

import strings

load_dotenv()


class LLMLogger:
    """
    Logger for OpenAI API calls with cost tracking and usage metrics.
    
    Logs all API interactions to a JSON file for monitoring usage,
    costs, and debugging purposes.
    """
    
    def __init__(self, llm: ChatOpenAI):
        """
        Initialize the logger with an LLM instance.
        
        Args:
            llm: ChatOpenAI instance to log calls for
        """
        self.llm = llm

    @staticmethod
    def log_request(prompts, parsed_reply: Dict[str, Dict]):
        """
        Log an API request with full details including cost calculation.
        
        Args:
            prompts: The input prompts sent to the API
            parsed_reply: Parsed response from the API
        """
        calls_log = os.path.join(os.getcwd(), "open_ai_calls.json")
        
        # Normalize prompts format
        if isinstance(prompts, StringPromptValue):
            prompts = prompts.text
        elif isinstance(prompts, Dict):
            prompts = {
                f"prompt_{i+1}": prompt.content
                for i, prompt in enumerate(prompts.messages)
            }
        else:
            prompts = {
                f"prompt_{i+1}": prompt.content
                for i, prompt in enumerate(prompts.messages)
            }

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Extract token usage and calculate costs
        token_usage = parsed_reply["usage_metadata"]
        output_tokens = token_usage["output_tokens"]
        input_tokens = token_usage["input_tokens"]
        total_tokens = token_usage["total_tokens"]

        model_name = parsed_reply["response_metadata"]["model_name"]
        prompt_price_per_token = 0.00000015
        completion_price_per_token = 0.0000006

        total_cost = (input_tokens * prompt_price_per_token) + (
            output_tokens * completion_price_per_token
        )

        # Create comprehensive log entry
        log_entry = {
            "model": model_name,
            "time": current_time,
            "prompts": prompts,
            "replies": parsed_reply["content"],
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_cost": total_cost,
        }

        # Append to log file
        with open(calls_log, "a", encoding="utf-8") as f:
            json_string = json.dumps(log_entry, ensure_ascii=False, indent=4)
            f.write(json_string + "\n")


class LoggerChatModel:
    """
    Wrapper for ChatOpenAI that logs all interactions.
    
    Provides the same interface as ChatOpenAI but automatically logs
    all requests and responses for monitoring and debugging.
    """

    def __init__(self, llm: ChatOpenAI):
        """
        Initialize with a ChatOpenAI instance.
        
        Args:
            llm: ChatOpenAI instance to wrap with logging
        """
        self.llm = llm

    def __call__(self, messages: List[Dict[str, str]]) -> str:
        """
        Call the LLM with logging.
        
        Args:
            messages: List of message dictionaries for the conversation
            
        Returns:
            AI response string
        """
        reply = self.llm(messages)
        parsed_reply = self.parse_llmresult(reply)
        LLMLogger.log_request(prompts=messages, parsed_reply=parsed_reply)
        return reply

    def parse_llmresult(self, llmresult: AIMessage) -> Dict[str, Dict]:
        """
        Parse LLM response into structured format for logging.
        
        Args:
            llmresult: AIMessage response from the LLM
            
        Returns:
            Structured dictionary with response details
        """
        content = llmresult.content
        response_metadata = llmresult.response_metadata
        id_ = llmresult.id
        usage_metadata = llmresult.usage_metadata

        parsed_result = {
            "content": content,
            "response_metadata": {
                "model_name": response_metadata.get("model_name", ""),
                "system_fingerprint": response_metadata.get("system_fingerprint", ""),
                "finish_reason": response_metadata.get("finish_reason", ""),
                "logprobs": response_metadata.get("logprobs", None),
            },
            "id": id_,
            "usage_metadata": {
                "input_tokens": usage_metadata.get("input_tokens", 0),
                "output_tokens": usage_metadata.get("output_tokens", 0),
                "total_tokens": usage_metadata.get("total_tokens", 0),
            },
        }
        return parsed_result


class GPTAnswerer:
    """
    AI-powered form response generator for LinkedIn Easy Apply.
    
    Uses OpenAI's GPT models to generate contextually appropriate responses
    to various types of application form questions based on resume data
    and job descriptions.
    
    Attributes:
        llm_cheap: LoggerChatModel instance for API calls
        resume: Resume data object
        job: Current job being applied to
    """
    
    def __init__(self, openai_api_key):
        """
        Initialize the GPT answerer with API credentials.
        
        Args:
            openai_api_key: OpenAI API key for authentication
        """
        self.llm_cheap = LoggerChatModel(
            ChatOpenAI(
                model_name="gpt-4o-mini", 
                openai_api_key=openai_api_key, 
                temperature=0.8
            )
        )

    @property
    def job_description(self):
        """Get the current job description."""
        return self.job.description

    @staticmethod
    def find_best_match(text: str, options: list[str]) -> str:
        """
        Find the best matching option using Levenshtein distance.
        
        Args:
            text: Text to match against
            options: List of possible options
            
        Returns:
            Best matching option from the list
        """
        distances = [
            (option, distance(text.lower(), option.lower())) for option in options
        ]
        best_option = min(distances, key=lambda x: x[1])[0]
        return best_option

    @staticmethod
    def _remove_placeholders(text: str) -> str:
        """Remove placeholder text from responses."""
        text = text.replace("PLACEHOLDER", "")
        return text.strip()

    @staticmethod
    def _preprocess_template_string(template: str) -> str:
        """Preprocess template strings to remove unnecessary indentation."""
        return textwrap.dedent(template)

    def set_resume(self, resume):
        """Set the resume data for context."""
        self.resume = resume

    def set_job(self, job):
        """
        Set the current job and generate job description summary.
        
        Args:
            job: Job object containing job details and description
        """
        self.job = job
        self.job.set_summarize_job_description(
            self.summarize_job_description(self.job.description)
        )

    def summarize_job_description(self, text: str) -> str:
        """
        Generate a summary of the job description.
        
        Args:
            text: Full job description text
            
        Returns:
            Summarized job description (currently returns first 100 chars)
        """
        if not text:
            self.current_summary = ""
            return self.current_summary
        output = text[:100]  # Simple truncation for now
        return output
    

    def get_resume_html(self):
        """
        Generate HTML resume tailored to the current job description.
        
        Returns:
            HTML-formatted resume string customized for the job
        """
        resume_markdown_prompt = ChatPromptTemplate.from_template(strings.resume_markdown_template)
        fusion_job_description_resume_prompt = ChatPromptTemplate.from_template(strings.fusion_job_description_resume_template)
        resume_markdown_chain = resume_markdown_prompt | self.llm_cheap | StrOutputParser()
        fusion_job_description_resume_chain = fusion_job_description_resume_prompt | self.llm_cheap | StrOutputParser()
        
        # Get template file paths
        casual_markdown_path = os.path.abspath("resume_template/casual_markdown.js")
        reorganize_header_path = os.path.abspath("resume_template/reorganizeHeader.js")
        resume_css_path = os.path.abspath("resume_template/resume.css")

        html_template = strings.html_template.format(
            casual_markdown=casual_markdown_path, 
            reorganize_header=reorganize_header_path, 
            resume_css=resume_css_path
        )
        
        composed_chain = (
            resume_markdown_chain
            | (lambda output: {"job_description": self.job.summarize_job_description, "formatted_resume": output})
            | fusion_job_description_resume_chain
            | (lambda formatted_resume: html_template + formatted_resume)
        )
        
        try:
            output = composed_chain.invoke({
                "resume": self.resume,
                "job_description": self.job.summarize_job_description
            })
            return output
        except Exception as e:
            pass  # Return None if generation fails

    def _create_chain(self, template: str):
        """
        Create a LangChain processing chain from a template.
        
        Args:
            template: Prompt template string
            
        Returns:
            Configured chain for processing
        """
        prompt = ChatPromptTemplate.from_template(template)
        return prompt | self.llm_cheap | StrOutputParser()

    def answer_question_textual_wide_range(self, question: str) -> str:
        """
        Answer a wide-range textual question by determining the relevant resume section.
        
        Args:
            question: Question text to answer
            
        Returns:
            AI-generated response based on relevant resume section
        """
        # Define chains for each resume section
        chains = {
            "personal_information": self._create_chain(strings.personal_information_template),
            "self_identification": self._create_chain(strings.self_identification_template),
            "legal_authorization": self._create_chain(strings.legal_authorization_template),
            "work_preferences": self._create_chain(strings.work_preferences_template),
            "education_details": self._create_chain(strings.education_details_template),
            "experience_details": self._create_chain(strings.experience_details_template),
            "projects": self._create_chain(strings.projects_template),
            "availability": self._create_chain(strings.availability_template),
            "salary_expectations": self._create_chain(strings.salary_expectations_template),
            "certifications": self._create_chain(strings.certifications_template),
            "languages": self._create_chain(strings.languages_template),
            "interests": self._create_chain(strings.interests_template),
            "cover_letter": self._create_chain(strings.coverletter_template),
        }
        
        # Determine which resume section is relevant
        section_prompt = (
            f"For the following question: '{question}', which section of the resume is relevant? "
            "Respond with one of the following: Personal information, Self Identification, Legal Authorization, "
            "Work Preferences, Education Details, Experience Details, Projects, Availability, Salary Expectations, "
            "Certifications, Languages, Interests, Cover letter"
        )
        prompt = ChatPromptTemplate.from_template(section_prompt)
        chain = prompt | self.llm_cheap | StrOutputParser()
        output = chain.invoke({"question": question})
        section_name = output.lower().replace(" ", "_")
        
        # Handle cover letter specially
        if section_name == "cover_letter":
            chain = chains.get(section_name)
            output = chain.invoke({"resume": self.resume, "job_description": self.job_description})
            return output
            
        # Get relevant resume section
        resume_section = getattr(self.resume, section_name, None)
        if resume_section is None:
            raise ValueError(f"Section '{section_name}' not found in the resume.")
            
        chain = chains.get(section_name)
        if chain is None:
            raise ValueError(f"Chain not defined for section '{section_name}'")
            
        return chain.invoke({"resume_section": resume_section, "question": question})

    def answer_question_textual(self, question: str) -> str:
        """
        Answer a general textual question using the entire resume.
        
        Args:
            question: Question text to answer
            
        Returns:
            AI-generated response based on resume data
        """
        template = self._preprocess_template_string(strings.resume_stuff_template)
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm_cheap | StrOutputParser()
        output = chain.invoke({"resume": self.resume, "question": question})
        return output

    def answer_question_numeric(self, question: str, default_experience: int = 3) -> int:
        """
        Answer a numeric question (e.g., years of experience).
        
        Args:
            question: Numeric question text
            default_experience: Default value if extraction fails
            
        Returns:
            Numeric answer extracted from AI response
        """
        func_template = self._preprocess_template_string(strings.numeric_question_template)
        prompt = ChatPromptTemplate.from_template(func_template)
        chain = prompt | self.llm_cheap | StrOutputParser()
        output_str = chain.invoke({
            "resume": self.resume, 
            "question": question, 
            "default_experience": default_experience
        })
        
        try:
            output = self.extract_number_from_string(output_str)
        except ValueError:
            output = default_experience
        return output

    def extract_number_from_string(self, output_str):
        """
        Extract the first number found in a string.
        
        Args:
            output_str: String potentially containing numbers
            
        Returns:
            First integer found in the string
            
        Raises:
            ValueError: If no numbers are found
        """
        numbers = re.findall(r"\d+", output_str)
        if numbers:
            return int(numbers[0])
        else:
            raise ValueError("No numbers found in the string")

    def answer_question_from_options(self, question: str, options: list[str]) -> str:
        """
        Answer a multiple choice question by selecting the best option.
        
        Args:
            question: Question text
            options: List of possible answer options
            
        Returns:
            Best matching option from the provided list
        """
        func_template = self._preprocess_template_string(strings.options_template)
        prompt = ChatPromptTemplate.from_template(func_template)
        chain = prompt | self.llm_cheap | StrOutputParser()
        output_str = chain.invoke({
            "resume": self.resume, 
            "question": question, 
            "options": options
        })
        best_option = self.find_best_match(output_str, options)
        return best_option
