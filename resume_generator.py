"""
Resume Generation Utilities

This module provides functions to generate custom PDF resumes
using the resumy package for each job application.
"""

import os
import subprocess
import sys
import tempfile
import yaml
from pathlib import Path
from datetime import datetime
from logging_config import logger


def get_repo_root():
    """Get the absolute path to the repository root."""
    return Path(__file__).parent.absolute()


def get_resumy_path():
    """Get the path to the resumy source directory."""
    repo_root = get_repo_root()
    resumy_src = repo_root / "resumy" / "src"
    return resumy_src


def generate_tailored_resume(company_name: str, job_title: str, tailored_config_yaml: str, output_dir: str = "tailored_resumes") -> str:
    """
    Generate a tailored PDF resume for a specific company and job.
    
    Args:
        company_name: Name of the company (used in filename)
        job_title: Job title (used in filename)
        tailored_config_yaml: YAML configuration content tailored for this job
        output_dir: Directory to save the generated files
        
    Returns:
        Path to the generated PDF file
        
    Raises:
        Exception: If resume generation fails
    """
    logger.info(f"[RESUME GEN] Starting resume generation for {company_name} - {job_title}")
    logger.debug(f"[RESUME GEN] Config YAML size: {len(tailored_config_yaml)} bytes")
    
    repo_root = get_repo_root()
    resumy_src = get_resumy_path()
    logger.debug(f"[RESUME GEN] Repo root: {repo_root}")
    logger.debug(f"[RESUME GEN] Resumy path: {resumy_src}")
    
    # Create output directory if it doesn't exist
    output_path = repo_root / output_dir
    output_path.mkdir(exist_ok=True)
    logger.debug(f"[RESUME GEN] Output directory: {output_path}")
    
    # Create safe filename (remove special characters and clean spaces)
    safe_company_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_company_name = "_".join(safe_company_name.split())  # Replace multiple spaces with single underscore
    
    safe_job_title = "".join(c for c in job_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_job_title = "_".join(safe_job_title.split())  # Replace multiple spaces with single underscore
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    base_filename = f"{safe_company_name}_{safe_job_title}_{timestamp}"
    config_filename = f"{base_filename}.yaml"
    pdf_filename = f"{base_filename}.pdf"
    
    config_path = output_path / config_filename
    pdf_path = output_path / pdf_filename
    
    logger.debug(f"[RESUME GEN] Config file: {config_path}")
    logger.debug(f"[RESUME GEN] PDF file: {pdf_path}")
    
    # Save the tailored configuration
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(tailored_config_yaml)
        logger.info(f"[RESUME GEN] Saved tailored config: {config_path}")
    except Exception as e:
        logger.error(f"[RESUME GEN ERROR] Failed to save tailored config: {e}")
        raise
    
    # Set up environment with resumy in PYTHONPATH
    env = os.environ.copy()
    current_path = env.get('PYTHONPATH', '')
    if current_path:
        env['PYTHONPATH'] = f"{resumy_src}:{current_path}"
    else:
        env['PYTHONPATH'] = str(resumy_src)
    logger.debug(f"[RESUME GEN] PYTHONPATH set to: {env['PYTHONPATH']}")
    
    # Get default theme path
    default_theme = repo_root / "resumy" / "mytheme"
    logger.debug(f"[RESUME GEN] Theme path: {default_theme}")
    
    # Prepare the resumy command
    cmd = [
        sys.executable, "-m", "resumy.resumy", "build",
        "-o", str(pdf_path),
        "--theme", str(default_theme),
        "--disable-validation",
        str(config_path)
    ]
    
    logger.info(f"[RESUME GEN] Generating resume PDF")
    logger.debug(f"[RESUME GEN] Command: {' '.join(cmd)}")
    
    try:
        # Run the command
        logger.debug("[RESUME GEN] Executing resumy build command")
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            env=env,
            check=True,
            capture_output=True,
            text=True
        )
        
        logger.info(f"[RESUME GEN] ✅ Resume generated successfully: {pdf_path}")
        if result.stdout:
            logger.debug(f"[RESUME GEN] Build output: {result.stdout[:500]}")
        
        # Verify file was created
        if pdf_path.exists():
            file_size = pdf_path.stat().st_size
            logger.debug(f"[RESUME GEN] PDF file size: {file_size} bytes")
        else:
            logger.error(f"[RESUME GEN ERROR] PDF file was not created at: {pdf_path}")
        
        return str(pdf_path)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[RESUME GEN ERROR] ❌ Error generating resume, return code: {e.returncode}")
        if e.stdout:
            logger.error(f"[RESUME GEN ERROR] STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"[RESUME GEN ERROR] STDERR: {e.stderr}")
        raise Exception(f"Failed to generate resume for {company_name}: {e}")
    except Exception as e:
        logger.error(f"[RESUME GEN ERROR] ❌ Unexpected error: {e}")
        logger.exception("[RESUME GEN ERROR] Full traceback:")
        raise


def validate_yaml_config(yaml_content: str) -> bool:
    """
    Validate that the YAML content is properly formatted.
    
    Args:
        yaml_content: YAML content string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        yaml.safe_load(yaml_content)
        return True
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML configuration: {e}")
        return False
    except Exception as e:
        logger.error(f"Error validating YAML: {e}")
        return False


def cleanup_old_resumes(output_dir: str = "tailored_resumes", max_files: int = 50):
    """
    Clean up old resume files to prevent disk space issues.
    
    Args:
        output_dir: Directory containing resume files
        max_files: Maximum number of files to keep (deletes oldest)
    """
    try:
        repo_root = get_repo_root()
        output_path = repo_root / output_dir
        
        if not output_path.exists():
            return
        
        # Get all PDF and YAML files
        files = list(output_path.glob("*.pdf")) + list(output_path.glob("*.yaml"))
        
        if len(files) <= max_files:
            return
        
        # Sort by modification time (oldest first)
        files.sort(key=lambda f: f.stat().st_mtime)
        
        # Delete oldest files
        files_to_delete = files[:len(files) - max_files]
        for file_path in files_to_delete:
            try:
                file_path.unlink()
                logger.debug(f"Deleted old resume file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")
                
        logger.info(f"Cleaned up {len(files_to_delete)} old resume files")
        
    except Exception as e:
        logger.warning(f"Error during resume cleanup: {e}")
