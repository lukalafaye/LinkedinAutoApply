# GPT Call System Analysis and Data Flow Documentation

## Overview
This document provides a comprehensive analysis of the GPT call system in the LinkedIn Auto Jobs Applier bot, including when calls are made, what data is used, and how the numeric answer handling works.

## System Architecture

### Resume Data Loading (resume.py)
- **Primary Data Source**: `data_folder/resume.yaml` (new JSON Resume format)
- **Configuration Data**: `data_folder/config.yaml` (bot-specific meta fields)
- **Data Model**: The `Resume` class converts the new YAML format to the expected data structure for GPT templates

### GPT Answerer Component (gpt.py)
- **Model**: Uses `gpt-4o-mini` with temperature 0.8 for balanced creativity and consistency
- **Cost Tracking**: All API calls are logged with token usage and cost calculations
- **Template System**: Uses LangChain with predefined prompt templates for different question types

## GPT Call Types and Data Flow

### 1. Personal Information Calls
**When triggered**: Radio/dropdown questions about basic personal info
**Template**: `personal_information_template`
**Data accessed**:
- `resume.personal_information.name`
- `resume.personal_information.surname` 
- `resume.personal_information.email`
- `resume.personal_information.phone`
- `resume.personal_information.address` (intentionally missing in test data)
- `resume.personal_information.city`
- `resume.personal_information.state`
- `resume.personal_information.country`

### 2. Self-Identification Calls
**When triggered**: Diversity/inclusion questions
**Template**: `self_identification_template`
**Data accessed**:
- `resume.self_identification.gender`
- `resume.self_identification.pronouns`
- `resume.self_identification.veteran`
- `resume.self_identification.disability`
- `resume.self_identification.ethnicity`

### 3. Legal Authorization Calls
**When triggered**: Work authorization questions
**Template**: `legal_authorization_template`
**Data accessed**:
- `resume.legal_authorization.euWorkAuthorization`
- `resume.legal_authorization.usWorkAuthorization`
- `resume.legal_authorization.requiresUsVisa`
- `resume.legal_authorization.legallyAllowedToWorkInUs`
- `resume.legal_authorization.requiresUsSponsorship`
- `resume.legal_authorization.requiresEuVisa`
- `resume.legal_authorization.legallyAllowedToWorkInEu`
- `resume.legal_authorization.requiresEuSponsorship`

### 4. Work Preferences Calls
**When triggered**: Questions about remote work, relocation, assessments
**Template**: `work_preferences_template`
**Data accessed**:
- `resume.work_preferences.remoteWork`
- `resume.work_preferences.inPersonWork`
- `resume.work_preferences.openToRelocation`
- `resume.work_preferences.willingToCompleteAssessments`
- `resume.work_preferences.willingToUndergoDrugTests`
- `resume.work_preferences.willingToUndergoBackgroundChecks`

### 5. Education Details Calls
**When triggered**: Questions about educational background
**Template**: `education_details_template`
**Data accessed**:
- `resume.education_details` (list of education entries)
- Each entry contains: degree, university, gpa, graduation_year, field_of_study, exam

### 6. Experience Details Calls
**When triggered**: Questions about work experience
**Template**: `experience_details_template`
**Data accessed**:
- `resume.experience_details` (list of work experience entries)
- Each entry contains: position, company, employmentPeriod, location, industry, keyResponsibilities, skillsAcquired

### 7. Projects Calls
**When triggered**: Questions about personal/professional projects
**Template**: `projects_template`
**Data accessed**:
- `resume.projects` (list of project entries)
- Each entry contains: name, description, link, keyTechnologies, keyResponsibilities

### 8. Availability Calls
**When triggered**: Questions about start date/notice period
**Template**: `availability_template`
**Data accessed**:
- `resume.availability.noticePeriod`

### 9. Salary Expectations Calls
**When triggered**: Compensation-related questions
**Template**: `salary_expectations_template`
**Data accessed**:
- `resume.salary_expectations.salaryRangeUSD`

### 10. Certifications Calls
**When triggered**: Questions about professional certifications
**Template**: `certifications_template`
**Data accessed**:
- `resume.certifications` (list of certification entries)
- Each entry contains: name, issuer, year, industry

### 11. Languages Calls
**When triggered**: Questions about language skills
**Template**: `languages_template`
**Data accessed**:
- `resume.languages` (list of language entries)
- Each entry contains: language, proficiency

### 12. Interests Calls
**When triggered**: Questions about personal interests
**Template**: `interests_template`
**Data accessed**:
- `resume.interests` (list of interest strings)

### 13. Cover Letter Generation
**When triggered**: Cover letter upload fields or specific questions
**Template**: `coverletter_template`
**Data accessed**:
- Complete resume data
- Current job description
- Job title and company information

### 14. Resume Generation
**When triggered**: Dynamic resume creation (currently disabled)
**Template**: `resume_markdown_template` + `fusion_job_description_resume_template`
**Data accessed**:
- Complete resume data
- Job description for customization

## Numeric Answer Handling System

### Problem Identified and Fixed
The original `numeric_question_template` contained contradictory instructions:
- "Answer the question directly (only number)" 
- "If you cannot answer, provide answers like 'I have no experience...'"

This could cause the LLM to return text instead of numbers.

### Solution Implemented
Updated the template to:
1. **Always return numbers only** - no text explanations
2. **Use 0 for no experience** - instead of text responses
3. **Provide clear examples** - showing both experience and no-experience cases
4. **Include rating guidance** - for 1-10 scale questions
5. **Reference default value** - use `{default_experience}` when uncertain

### Code Flow for Numeric Answers

1. **Detection**: Field with `id` containing "-numeric" triggers numeric handling
2. **GPT Call**: `answer_question_numeric()` uses improved template
3. **Extraction**: `extract_number_from_string()` finds first number in response using regex `\d+`
4. **Validation**: If no number found, falls back to `default_experience` (default: 3)
5. **Clamping**: `_clamp_numeric_answer()` ensures result is within acceptable range (1-99)
6. **Type Safety**: Result is always converted to string for form input

### Error Handling
- **ValueError in extraction** → Uses default value (3)
- **Invalid float/int conversion** → Uses minimum value (1)
- **Out of range** → Clamped to min/max bounds
- **Empty response** → Defaults to "0"

## Application Process Flow

### Job Discovery Phase
1. **Search Setup**: `LinkedInJobManager.start_applying()` configures search parameters
2. **Page Iteration**: Loads job listings page by page
3. **Job Extraction**: `extract_job_information_from_tile()` gets job metadata
4. **Filtering**: Applies blacklists for companies and titles

### Application Phase
1. **Job Selection**: `LinkedInJobManager.apply_jobs()` processes each job
2. **Navigation**: `LinkedInEasyApplier.job_apply()` opens job page
3. **Description Extraction**: `_get_job_description()` gets full job text
4. **GPT Setup**: `gpt_answerer.set_job()` provides job context
5. **Form Processing**: `_fill_application_form()` handles multi-step forms

### Form Step Processing
1. **Form Detection**: Finds `<form>` element for current step
2. **Element Scanning**: `_answer_visible_form()` processes all form elements
3. **Type Detection**: Delegates to specific handlers based on element type
4. **Answer Generation**: Calls appropriate GPT method based on question type
5. **Answer Persistence**: `_remember_answer()` saves new responses
6. **Step Advancement**: `_next_or_submit()` proceeds to next step

### GPT Call Triggers

**Radio Questions** → `answer_question_from_options()`
- Uses `options_template`
- Selects best match from provided options

**Text Questions** → `answer_question_textual_wide_range()`
- Determines relevant resume section
- Uses section-specific template
- Provides contextual response

**Numeric Questions** → `answer_question_numeric()`
- Uses improved `numeric_question_template`
- Always returns integer value
- Handles experience/rating questions

**Dropdown Questions** → `answer_question_from_options()`
- Same as radio questions
- Avoids placeholder options

**Multiline Questions** → `answer_question_textual_wide_range()`
- For longer text responses
- Cover letter style answers

## Data Validation Results

### Test Coverage
- ✅ All 13 GPT call types successfully access required data
- ✅ YAML/config structure properly mapped to expected format
- ✅ Resume data conversion functions working correctly
- ✅ Template placeholders match available data fields
- ⚠️ Address field intentionally missing (expected behavior)

### Improvements Made
1. **Fixed numeric template** to always return numbers
2. **Added comprehensive examples** for different numeric scenarios
3. **Improved error handling** in numeric extraction
4. **Enhanced documentation** of data flow and call patterns

## Recommendations

### For Production Use
1. **API Key Management**: Implement proper secrets management for OpenAI API key
2. **Rate Limiting**: Add delays between API calls to avoid hitting rate limits
3. **Cost Monitoring**: Set up alerts for API usage costs
4. **Template Testing**: Regular validation of prompt templates with real scenarios
5. **Error Recovery**: Enhanced fallback strategies for API failures

### For Maintenance
1. **Regular Template Updates**: Keep prompt templates aligned with LinkedIn form changes
2. **Data Structure Validation**: Ensure resume YAML format stays compatible
3. **Performance Monitoring**: Track API response times and success rates
4. **Answer Quality Review**: Periodic review of generated responses for accuracy

## Conclusion

The GPT call system is now fully compatible with the new resume.yaml format and properly handles all question types. The numeric answer handling has been significantly improved to ensure consistent, reliable numeric responses. All data flows have been verified and documented for future maintenance and development.
