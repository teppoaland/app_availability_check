#!/usr/bin/env python3
"""
Allure Operations Handler - Complete Allure report generation and history management
"""

import json
import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

def log_message(message, verbose=True):
    """Print message for GitHub Actions UI"""
    if verbose:
        print(f"[ALLURE-OPS] {message}")
        sys.stdout.flush()

def run_command(command, check=True, verbose=True):
    """Run shell command with proper error handling"""
    log_message(f"Executing: {command}", verbose)
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            check=check
        )
        if result.stdout:
            log_message(f"Output: {result.stdout}", verbose)
        if result.stderr:
            log_message(f"Errors: {result.stderr}", verbose)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        log_message(f"Command failed: {e}", verbose)
        if check:
            raise
        return False

def install_allure_commandline(verbose=True):
    """Install Allure commandline tool"""
    log_message("Installing Allure commandline...", verbose)
    return run_command("npm install -g allure-commandline", verbose=verbose)

def generate_allure_report(results_dir="allure-results", report_dir="allure-report", verbose=True):
    """Generate Allure report with proper error handling"""
    log_message(f"Generating Allure report from {results_dir} to {report_dir}", verbose)
    
    # Check if results directory exists and has files
    results_path = Path(results_dir)
    if not results_path.exists() or not any(results_path.iterdir()):
        log_message(f"Warning: {results_dir} is empty or doesn't exist", verbose)
        return False
    
    # Generate report
    success = run_command(
        f"allure generate {results_dir} --clean -o {report_dir}",
        verbose=verbose
    )
    
    if success:
        log_message(f"Allure report generated successfully in {report_dir}", verbose)
        
        # Verify report was created
        report_path = Path(report_dir)
        if report_path.exists() and any(report_path.iterdir()):
            log_message("Report directory contains files", verbose)
            return True
        else:
            log_message("Warning: Report directory is empty after generation", verbose)
            return False
    else:
        log_message("Failed to generate Allure report", verbose)
        return False

def handle_history_artifacts(report_dir="allure-report", artifact_name="allure-history", verbose=True):
    """Handle history artifacts upload preparation"""
    log_message("Preparing history artifacts...", verbose)
    
    history_dir = Path(report_dir) / "history"
    if history_dir.exists() and any(history_dir.iterdir()):
        log_message(f"History found in {history_dir}", verbose)
        return True
    else:
        log_message(f"Warning: No history found in {history_dir}", verbose)
        return False

def main():
    """Main function to handle Allure operations"""
    parser = argparse.ArgumentParser(description='Allure Report Operations')
    parser.add_argument('--install', action='store_true', help='Install Allure commandline')
    parser.add_argument('--generate', action='store_true', help='Generate Allure report')
    parser.add_argument('--results-dir', default='allure-results', help='Allure results directory')
    parser.add_argument('--report-dir', default='allure-report', help='Allure report directory')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    verbose = args.verbose
    
    success = True
    
    if args.install:
        success &= install_allure_commandline(verbose)
    
    if args.generate:
        success &= generate_allure_report(args.results_dir, args.report_dir, verbose)
        success &= handle_history_artifacts(args.report_dir, verbose=verbose)
    
    if success:
        log_message("All operations completed successfully", verbose)
        sys.exit(0)
    else:
        log_message("Some operations failed", verbose)
        sys.exit(1)

if __name__ == '__main__':
    main()