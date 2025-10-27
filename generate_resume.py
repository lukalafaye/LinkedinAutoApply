#!/usr/bin/env python3
"""
Resume Generator Script

This script generates a PDF resume using the local resumy package.
It automatically handles path configuration and runs resumy build command
with the specified parameters.

Usage:
    python generate_resume.py [--config CONFIG_FILE] [--output OUTPUT_FILE] [--theme THEME_PATH]

Examples:
    python generate_resume.py
    python generate_resume.py --config custom_config.yaml --output my_resume.pdf
    python generate_resume.py --theme /path/to/custom/theme --config mydata.yaml
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path


def get_repo_root():
    """Get the absolute path to the repository root."""
    return Path(__file__).parent.absolute()


def get_resumy_path():
    """Get the path to the resumy source directory."""
    repo_root = get_repo_root()
    resumy_src = repo_root / "resumy" / "src"
    return resumy_src


def get_default_config():
    """Get the default config file path."""
    repo_root = get_repo_root()
    default_config = repo_root / "resumy" / "myconfig.yaml"
    return default_config


def get_default_theme():
    """Get the default theme path."""
    repo_root = get_repo_root()
    default_theme = repo_root / "resumy" / "mytheme"
    return default_theme


def run_resumy_build(config_file, output_file, theme_path, disable_validation=True):
    """
    Run resumy build command with the specified parameters.
    
    Args:
        config_file: Path to the config YAML file
        output_file: Output PDF file path
        theme_path: Path to the theme directory
        disable_validation: Whether to disable validation
    
    Returns:
        True if successful, False otherwise
    """
    resumy_src = get_resumy_path()
    
    # Add resumy source to Python path
    env = os.environ.copy()
    current_path = env.get('PYTHONPATH', '')
    if current_path:
        env['PYTHONPATH'] = f"{resumy_src}:{current_path}"
    else:
        env['PYTHONPATH'] = str(resumy_src)
    
    # Prepare the command
    cmd = [
        sys.executable, "-m", "resumy.resumy", "build",
        "-o", str(output_file),
        "--theme", str(theme_path),
    ]
    
    if disable_validation:
        cmd.append("--disable-validation")
    
    cmd.append(str(config_file))
    
    print(f"Running command: {' '.join(cmd)}")
    print(f"Working directory: {get_repo_root()}")
    print(f"PYTHONPATH: {env['PYTHONPATH']}")
    print(f"Config file: {config_file}")
    print(f"Output file: {output_file}")
    print(f"Theme path: {theme_path}")
    print("-" * 50)
    
    try:
        # Run the command
        result = subprocess.run(
            cmd,
            cwd=get_repo_root(),
            env=env,
            check=True,
            capture_output=True,
            text=True
        )
        
        print("✅ Resume generated successfully!")
        if result.stdout:
            print("Output:", result.stdout)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running resumy: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def validate_paths(config_file, theme_path):
    """
    Validate that the specified paths exist.
    
    Args:
        config_file: Path to config file
        theme_path: Path to theme directory
        
    Returns:
        True if all paths are valid, False otherwise
    """
    config_path = Path(config_file)
    theme_dir = Path(theme_path)
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_file}")
        return False
    
    if not theme_dir.exists():
        print(f"❌ Theme directory not found: {theme_path}")
        return False
    
    if not theme_dir.is_dir():
        print(f"❌ Theme path is not a directory: {theme_path}")
        return False
    
    return True


def main():
    """Main function to handle command line arguments and run resumy."""
    parser = argparse.ArgumentParser(
        description="Generate PDF resume using local resumy package",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --config custom_config.yaml --output my_resume.pdf
  %(prog)s --theme /path/to/custom/theme --config mydata.yaml
  %(prog)s --output professional_resume.pdf --no-disable-validation
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help=f"Path to config YAML file (default: {get_default_config()})"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="generated_resume.pdf",
        help="Output PDF file name (default: generated_resume.pdf)"
    )
    
    parser.add_argument(
        "--theme", "-t",
        type=str,
        default=None,
        help=f"Path to theme directory (default: {get_default_theme()})"
    )
    
    parser.add_argument(
        "--no-disable-validation",
        action="store_true",
        help="Enable validation (default: validation is disabled)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Set defaults if not provided
    config_file = args.config if args.config else get_default_config()
    theme_path = args.theme if args.theme else get_default_theme()
    output_file = args.output
    disable_validation = not args.no_disable_validation
    
    if args.verbose:
        print("Configuration:")
        print(f"  Config file: {config_file}")
        print(f"  Output file: {output_file}")
        print(f"  Theme path: {theme_path}")
        print(f"  Disable validation: {disable_validation}")
        print(f"  Repository root: {get_repo_root()}")
        print(f"  Resumy source: {get_resumy_path()}")
        print()
    
    # Validate paths
    if not validate_paths(config_file, theme_path):
        sys.exit(1)
    
    # Run resumy build
    success = run_resumy_build(config_file, output_file, theme_path, disable_validation)
    
    if success:
        output_path = get_repo_root() / output_file
        print(f"📄 Resume saved to: {output_path}")
        sys.exit(0)
    else:
        print("❌ Failed to generate resume")
        sys.exit(1)


if __name__ == "__main__":
    main()
