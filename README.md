# LinkedIn Auto Job Applier with AI

Automate your LinkedIn job applications with AI-powered resume tailoring and intelligent form filling.

## Quick Start

### Prerequisites
- Python 3.9 or higher
- Google Chrome browser
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- LinkedIn account with language set to **English**

### Installation

1. **Clone and install:**
   ```bash
   git clone https://github.com/lukalafaye/LinkedinAutoApply
   cd LinkedinAutoApply
   pip install -r requirements.txt
   ```
2. **Set up your configuration files:**

   Copy the example files from `data_folder_example/` to create your own `data_folder/`:
   ```bash
   cp -r data_folder_example data_folder
   ```

3. **Edit your credentials in `data_folder/secrets.yaml`:**
   ```yaml
   email: your.linkedin@email.com
   password: your_linkedin_password
   openai_api_key: sk-your-openai-api-key
   ```
   > ⚠️ Never commit this file to version control!

4. **Configure your job search in `data_folder/config.yaml`:**
   ```yaml
   remote: true
   positions:
     - Software Engineer
     - Data Scientist
   locations:
     - New York
     - Remote
   distance: 50
   ```

5. **Add your resume information in `data_folder/resume.yaml`:**
   ```yaml
   basics:
     name: "Your Name"
     email: "your.email@example.com"
     phone: "+1234567890"
     location:
       city: "Your City"
       countryCode: "US"
   
   work:
     - name: "Company Name"
       position: "Job Title"
       startDate: "2022-01-01"
       summary: "Job description"
   
   education:
     - institution: "University Name"
       area: "Computer Science"
       studyType: "Bachelor"
   
   skills:
     - name: "Languages"
       keywords: ["Python", "JavaScript"]
   ```

## Usage

### Run with AI Resume Tailoring (Recommended)

The bot automatically generates a custom resume for each job:

```bash
python main.py
```

**What it does:**
- 🎯 Analyzes each job description
- ✏️ Tailors your resume to match requirements
- 📄 Generates a custom PDF for each application
- 🤖 Fills forms intelligently using GPT
- 💾 Saves all tailored resumes in `tailored_resumes/` folder

### Run with Static Resume

Use the same PDF for all applications:

```bash
python main.py --resume /path/to/your/resume.pdf
```

### Generate Resume Only

Test resume generation without applying:

```bash
python generate_resume.py
python generate_resume.py --output my_resume.pdf
```

## Features

✅ **Smart Form Filling**
- Detects dropdowns, text fields, and autocomplete fields
- Handles multilingual forms (English, French, Spanish, etc.)
- Saves answers to speed up future applications

✅ **AI-Powered**
- GPT integration for intelligent answers
- Resume tailoring for each job
- Handles complex questions automatically

✅ **Reliable**
- Comprehensive error handling
- Debug HTML dumps on errors
- Detailed logging for troubleshooting

✅ **Configurable**
- Filter jobs by type, experience, location
- Blacklist companies or job titles
- Set application limits

## Configuration Reference

### Job Search Filters (`config.yaml`)

```yaml
# Job preferences
remote: true
experienceLevel:
  internship: false
  entry: true
  associate: true
  mid-senior level: true
  director: false
  executive: false

jobTypes:
  full-time: true
  contract: false
  part-time: false
  temporary: false
  internship: false
  other: false
  volunteer: false

date:
  all time: false
  month: false
  week: true
  24 hours: false

# Search parameters
positions:
  - Machine Learning Engineer
  - AI Researcher
locations:
  - Paris
  - Remote
distance: 50

# Filters
companyBlacklist:
  - Company To Avoid
titleBlacklist:
  - Sales
  - Marketing
```

## Troubleshooting

**Bot fails on forms:**
- Check `debug_html/` folder for HTML dumps
- Review `log.txt` for detailed error messages
- Ensure LinkedIn language is set to English

**API quota exceeded:**
- Add credits to your OpenAI account at [billing dashboard](https://platform.openai.com/account/billing)
- Consider using a static resume to reduce API calls

**ChromeDriver issues:**
- Ensure Chrome is installed in default location
- Update Chrome to the latest version

**Validation errors:**
- Check saved answers in `data_folder/output/old_Questions.csv`
- Remove any placeholder answers (e.g., "Select an option")

## File Structure

```
LinkedinAutoApply/
├── data_folder/              # Your configuration (created from example)
│   ├── secrets.yaml         # LinkedIn & OpenAI credentials
│   ├── config.yaml          # Job search configuration
│   └── resume.yaml          # Your resume information
├── data_folder_example/      # Example configurations
├── tailored_resumes/         # AI-generated custom resumes
├── debug_html/               # HTML dumps for debugging
├── main.py                   # Main bot script
├── generate_resume.py        # Standalone resume generator
└── log.txt                   # Detailed execution logs
```

## Tips for Best Results

1. **Resume Quality:** Provide detailed information in `resume.yaml` - the AI uses this to tailor applications
2. **Job Titles:** Use specific position titles that match LinkedIn job postings
3. **Monitor Logs:** Check `log.txt` regularly to understand what the bot is doing
4. **Review Tailored Resumes:** Check `tailored_resumes/` folder to see how AI adapts your resume
5. **Start Small:** Begin with a limited search (1-2 positions, 1 location) to test

## Credits

- **casual-markdown:** Lightweight Markdown parser by [casualwriter](https://github.com/casualwriter/casual-markdown)
- Built on top of Selenium WebDriver and OpenAI GPT APIs

---

**Note:** This tool is for educational purposes. Users are responsible for complying with LinkedIn's terms of service and applicable laws.
