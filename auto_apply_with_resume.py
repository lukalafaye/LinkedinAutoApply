#!/usr/bin/env python3
"""
Auto Resume Generator and Job Applier

This script combines resume generation with automatic job application.
It first generates a custom PDF resume using resumy, then runs the LinkedIn bot
with the generated resume.

Usage:
    python auto_apply_with_resume.py [--config CONFIG] [--theme THEME] [--output OUTPUT]

Examples:
    python auto_apply_with_resume.py
    python auto_apply_with_resume.py --config custom_resume.yaml --output professional.pdf
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_repo_root():
    """Get the absolute path to the repository root."""
    return Path(__file__).parent.absolute()


def main():
    """Main function to generate resume and run job application bot."""
    parser = argparse.ArgumentParser(
        description="Generate resume and run LinkedIn job application bot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="resumy/myconfig.yaml",
        help="Path to resume config YAML file (default: resumy/myconfig.yaml)"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="auto_generated_resume.pdf",
        help="Output PDF file name (default: auto_generated_resume.pdf)"
    )
    
    parser.add_argument(
        "--theme", "-t",
        type=str,
        default="resumy/mytheme",
        help="Path to theme directory (default: resumy/mytheme)"
    )
    
    parser.add_argument(
        "--skip-resume",
        action="store_true",
        help="Skip resume generation and use existing file"
    )
    
    args = parser.parse_args()
    
    repo_root = get_repo_root()
    resume_path = repo_root / args.output
    
    if not args.skip_resume:
        print("🔧 Step 1: Generating resume...")
        
        # Generate resume using our generate_resume.py script
        resume_cmd = [
            sys.executable, "generate_resume.py",
            "--config", args.config,
            "--output", args.output,
            "--theme", args.theme
        ]
        
        try:
            result = subprocess.run(resume_cmd, cwd=repo_root, check=True)
            print("✅ Resume generated successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to generate resume: {e}")
            sys.exit(1)
    else:
        if not resume_path.exists():
            print(f"❌ Resume file not found: {resume_path}")
            print("Either remove --skip-resume or ensure the file exists.")
            sys.exit(1)
        print(f"📄 Using existing resume: {resume_path}")
    
    print("🤖 Step 2: Starting LinkedIn job application bot...")
    
    # Run the main LinkedIn bot with the generated resume
    bot_cmd = [
        sys.executable, "main.py",
        "--resume", str(resume_path)
    ]
    
    try:
        subprocess.run(bot_cmd, cwd=repo_root, check=True)
        print("✅ Job application process completed!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Job application failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Job application interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
