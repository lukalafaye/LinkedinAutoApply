## Installation

1. **Download and Install Python:**

   Ensure you have Python installed. If not, download and install it from Python's official website. For detailed instructions, refer to the tutorials:

   - [How to Install Python on Windows](https://www.geeksforgeeks.org/how-to-install-python-on-windows/)
   - [How to Install Python on Linux](https://www.geeksforgeeks.org/how-to-install-python-on-linux/)
   - [How to Download and Install Python on macOS](https://www.geeksforgeeks.org/how-to-download-and-install-python-latest-version-on-macos-mac-os-x/)

2. **Download and Install Google Chrome:**
   - Download and install the latest version of Google Chrome in its default location from the [official website](https://www.google.com/chrome).

3. **Clone the repository:**
   ```bash
   git clone https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application
   cd LinkedIn_AIHawk_automatic_job_application
   ```

4. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### 1. secrets.yaml

This file contains sensitive information. Never share or commit this file to version control.

- `email: [Your LinkedIn email]`
  - Replace with your LinkedIn account email address
- `password: [Your LinkedIn password]`
  - Replace with your LinkedIn account password
- `openai_api_key: [Your OpenAI API key]`
  - Replace with your OpenAI API key for GPT integration
  - To obtain an API key, follow the tutorial at: https://medium.com/@lorenzozar/how-to-get-your-own-openai-api-key-f4d44e60c327
  - Note: You need to add credit to your OpenAI account to use the API. You can add credit by visiting the [OpenAI billing dashboard](https://platform.openai.com/account/billing).



### 2. config.yaml

This file defines your job search parameters and bot behavior. Each section contains options that you can customize:

- `remote: [true/false]`
  - Set to `true` to include remote jobs, `false` to exclude them

- `experienceLevel:`
  - Set desired experience levels to `true`, others to `false`

- `jobTypes:`
  - Set desired job types to `true`, others to `false`

- `date:`
  - Choose one time range for job postings by setting it to `true`, others to `false`


- `positions:`
  - List job titles you're interested in, one per line
  - Example:
    ```yaml
    positions:
      - Software Developer
      - Data Scientist
    ```

- `locations:`
  - List locations you want to search in, one per line
  - Example:
    ```yaml
    locations:
      - Italy
      - London
    ```

- `distance: [number]`
  - Set the radius for your job search in miles
  - Example: `distance: 50`

- `companyBlacklist:`
  - List companies you want to exclude from your search, one per line
  - Example:
    ```yaml
    companyBlacklist:
      - Company X
      - Company Y
    ```

- `titleBlacklist:`
  - List keywords in job titles you want to avoid, one per line
  - Example:
    ```yaml
    titleBlacklist:
      - Sales
      - Marketing
    ```

### 3. plain_text_resume.yaml

This file contains your resume information in a structured format. Fill it out with your personal details, education, work experience, and skills. This information is used to auto-fill application forms and generate customized resumes.

Each section has specific fields to fill out:

- `personal_information:`
  - Contains basic personal details
  - Example: `name: "John Doe"`

- `self_identification:`
  - Optional demographic information
  - Example: `gender: "Male"`

- `legal_authorization:`
  - Work authorization status
  - Use `true` or `false` for each field
  - Example: `usWorkAuthorization: true`

- `work_preferences:`
  - Your work-related preferences
  - Use `true` or `false` for each field
  - Example: `remoteWork: true`

- `education_details:`
  - List your educational background
  - Include degree, university, GPA, graduation year, field of study, and skills acquired
  - Example:
    ```yaml
    - degree: "Bachelor's"
      university: "University of Example"
      gpa: "3.8"
      graduationYear: "2022"
      fieldOfStudy: "Computer Science"
      skillsAcquired:
        problemSolving: "4"
    ```

- `experience_details:`
  - List your work experiences
  - Include position, company, employment period, location, industry, key responsibilities, and skills acquired
  - Example:
    ```yaml
    - position: "Software Developer"
      company: "Tech Corp"
      employmentPeriod: "Jan 2020 - Present"
      location: "San Francisco, USA"
      industry: "Technology"
      keyResponsibilities:
        responsibility1: "Developed web applications using React"
      skillsAcquired:
        adaptability: "3"
    ```

- Other sections like `projects`, `availability`, `salary_expectations`, `certifications`, `skills`, `languages`, and `interests` follow a similar format, with each item on a new line.

### PLUS. data_folder_example

The `data_folder_example` folder contains a working example of how the files necessary for the bot's operation should be structured and filled out. This folder serves as a practical reference to help you correctly set up your work environment for the LinkedIn job search bot.

#### Contents

Inside this folder, you'll find example versions of the key files:

- `secrets.yaml`
- `config.yaml`
- `plain_text_resume.yaml`

These files are already populated with fictitious but realistic data. They show you the correct format and type of information to enter in each file.

#### Usage

Using this folder as a guide can be particularly helpful for:

1. Understanding the correct structure of each configuration file
2. Seeing examples of valid data for each field
3. Having a reference point while filling out your personal files

#### Important Note

## Usage
0. **LinkedIn language**
   To ensure the bot works, your LinkedIn language must be set to English.
   
2. **Data Folder:**
   Ensure that your data_folder contains the following files:
   - `secrets.yaml`
   - `config.yaml`
   - `plain_text_resume.yaml`

3. **Run the Bot:**

   LinkedIn_AIHawk offers flexibility in how it handles your pdf resume:

- **Dynamic Resume Generation:**
  If you don't use the `--resume` option, the bot will automatically generate a unique resume for each application. This feature uses the information from your `plain_text_resume.yaml` file and tailors it to each specific job application, potentially increasing your chances of success by customizing your resume for each position.
   ```bash
   python main.py
   ```
- **Using a Specific Resume:**
  If you want to use a specific PDF resume for all applications, run the bot with the `--resume` option:
  ```bash
  python main.py --resume /path/to/your/resume.pdf
  ```

## Documentation

For detailed information on each component and their respective roles, please refer to the [Documentation](documentation.md) file.

## Troubleshooting

- **ChromeDriver Issues:** Ensure ChromeDriver is compatible with your installed Chrome version.
- **Missing Files:** Verify that all necessary files are present in the data folder.
- **Invalid YAML:** Check your YAML files for syntax errors.

## Credits

### casual-markdown
- **Description:** This project uses the casual-markdown library, a lightweight regex-based Markdown parser with Table of Contents (TOC) support.
- **Author:** [casualwriter](https://github.com/casualwriter)
- **Repository:** [casual-markdown](https://github.com/casualwriter/casual-markdown)

## Disclaimer
Developed for educational purposes only. I do not assume any responsibility for this tool use. Users should ensure they comply with LinkedIn's terms of service, any applicable laws and regulations, and ethical considerations when using this tool.
