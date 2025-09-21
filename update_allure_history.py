#!/usr/bin/env python3
"""
Allure History Manager - Complete with Post-Generation Cleanup
1. Verifies the history directory structure.
2. Checks if previous history was downloaded successfully from the artifact.
3. Manages history-trend.json buildOrder incrementation.
4. Cleans up malformed data that Allure adds during report generation.
"""

import json
import os
import sys
import argparse
from pathlib import Path

def log_message(message, verbose=True):
    """Print message for GitHub Actions UI"""
    if verbose:
        print(f"[ALLURE-HISTORY] {message}")
        sys.stdout.flush()

def clean_history_trend(history_trend):
    """Clean and validate history trend entries"""
    cleaned = []
    for entry in history_trend:
        # Only keep entries with proper buildOrder structure
        if isinstance(entry, dict) and 'buildOrder' in entry and 'data' in entry:
            # Ensure all required fields exist
            if all(key in entry for key in ['buildOrder', 'reportName', 'reportUrl', 'data']):
                cleaned.append(entry)
    return cleaned

def clean_post_allure_generation(verbose=True):
    """Clean history after Allure report generation - fixes Allure's malformed entries"""
    log_message("Starting post-generation history cleanup...", verbose)
    
    # Path to the generated report history
    report_history_dir = Path('./allure-report/history')
    trend_file = report_history_dir / 'history-trend.json'
    
    if not trend_file.exists():
        log_message("No history-trend.json found in report. Nothing to fix.", verbose)
        return 0
    
    try:
        with open(trend_file, 'r', encoding='utf-8') as f:
            allure_data = json.load(f)
        log_message(f"Loaded history-trend.json with {len(allure_data)} entries", verbose)
        
        # Separate the entries
        valid_entries = []
        test_data_entries = []
        
        for entry in allure_data:
            if isinstance(entry, dict):
                if 'buildOrder' in entry and 'reportName' in entry:
                    # This is a properly formatted entry from our script
                    valid_entries.append(entry)
                elif 'data' in entry and 'buildOrder' not in entry:
                    # This is test data that Allure added without proper structure
                    test_data_entries.append(entry)
                    log_message(f"Found malformed entry (missing buildOrder): {entry}", verbose)
        
        log_message(f"Found {len(valid_entries)} valid entries and {len(test_data_entries)} malformed entries", verbose)
        
        # Merge real test data into valid entries
        if valid_entries and test_data_entries:
            # Sort valid entries by buildOrder to get the latest
            valid_entries.sort(key=lambda x: x.get('buildOrder', 0))
            latest_entry = valid_entries[-1]
            
            # Use the most recent test data (Allure's actual results)
            if test_data_entries:
                latest_test_data = test_data_entries[-1]['data']
                latest_entry['data'] = latest_test_data
                log_message(f"Updated buildOrder {latest_entry['buildOrder']} with real test data: passed={latest_test_data.get('passed', 0)}, failed={latest_test_data.get('failed', 0)}, total={latest_test_data.get('total', 0)}", verbose)
        
        # Keep only valid entries, sorted by buildOrder
        valid_entries.sort(key=lambda x: x.get('buildOrder', 0))
        
        # Save the cleaned data
        with open(trend_file, 'w', encoding='utf-8') as f:
            json.dump(valid_entries, f, indent=2, ensure_ascii=False)
        
        log_message(f"SUCCESS: Cleaned and saved {len(valid_entries)} valid entries", verbose)
        
        # Show final result
        for entry in valid_entries:
            total = entry['data']['total']
            passed = entry['data']['passed']
            failed = entry['data']['failed']
            build_order = entry['buildOrder']
            log_message(f"  BuildOrder {build_order}: {total} tests ({passed} passed, {failed} failed)", verbose)
        
        return len(valid_entries)
        
    except Exception as e:
        log_message(f"ERROR: Failed to clean post-generation history: {e}", verbose)
        import traceback
        traceback.print_exc()
        return 0

def manage_allure_history(verbose=True):
    log_message("Starting complete Allure history management...", verbose)
    
    # Path to history files
    history_dir = Path('./allure-results/history')
    trend_file = history_dir / 'history-trend.json'
    history_file = history_dir / 'history.json'
    
    # 1. Ensure the directory exists
    history_dir.mkdir(parents=True, exist_ok=True)
    log_message(f"Ensured directory exists: {history_dir}", verbose)
    
    # 2. CHECK if history was downloaded from git storage
    downloaded_files = list(history_dir.glob('*.json'))
    history_downloaded = len(downloaded_files) > 0
    
    if history_downloaded:
        log_message("SUCCESS: History files found from git storage download.", verbose)
        for file in downloaded_files:
            log_message(f"   - Found: {file.name}", verbose)
    else:
        log_message("INFO: No history files found. This is expected on the first run.", verbose)
    
    # 3. Initialize or load history-trend.json
    if trend_file.exists():
        try:
            with open(trend_file, 'r', encoding='utf-8') as f:
                raw_history = json.load(f)
            
            # Clean the history data
            history_trend = clean_history_trend(raw_history)
            
            if history_trend:
                # Find max buildOrder from valid entries
                max_order = max(item.get('buildOrder', 0) for item in history_trend)
                log_message(f"Loaded and cleaned history trend with {len(history_trend)} valid entries. Max buildOrder: {max_order}", verbose)
                if len(raw_history) != len(history_trend):
                    log_message(f"Removed {len(raw_history) - len(history_trend)} invalid entries.", verbose)
            else:
                # No valid entries found
                history_trend = []
                max_order = 0
                log_message("No valid entries found in existing history. Starting fresh.", verbose)
                
        except (json.JSONDecodeError, Exception) as e:
            log_message(f"Error loading {trend_file}: {e}. Creating new history.", verbose)
            history_trend = []
            max_order = 0
    else:
        # No trend file exists (first run or download failed)
        log_message("No history-trend.json file found. Creating new history.", verbose)
        history_trend = []
        max_order = 0
    
    # 4. Create new entry for THIS run
    new_order = max_order + 1
    new_entry = {
        'buildOrder': new_order,
        'reportName': f'Run #{new_order}',
        'reportUrl': f'https://github.com/{os.environ.get("GITHUB_REPOSITORY", "user/repo")}/actions/runs/{os.environ.get("GITHUB_RUN_ID", "1")}',
        'data': { 
            # Placeholder data - Allure will fill this with real data during report generation
            'failed': 0, 'broken': 0, 'skipped': 0, 
            'passed': 0, 'unknown': 0, 'total': 0
        }
    }
    
    log_message(f"Creating new trend entry with buildOrder: {new_order}", verbose)
    
    # Add new entry and keep only recent history (last 10 runs)
    history_trend.append(new_entry)
    history_trend = history_trend[-10:]  # Keep only last 10 runs
    log_message(f"History trend now contains {len(history_trend)} entries.", verbose)
    
    # 5. Save the updated and cleaned trend file
    with open(trend_file, 'w', encoding='utf-8') as f:
        json.dump(history_trend, f, indent=2, ensure_ascii=False)
    log_message(f"Saved cleaned and updated history trend to: {trend_file}", verbose)
    
    # 6. Create other required Allure history files
    duration_trend_file = history_dir / 'duration-trend.json'
    categories_trend_file = history_dir / 'categories-trend.json'
    
    # Create duration trend if it doesn't exist
    if not duration_trend_file.exists():
        with open(duration_trend_file, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        log_message(f"Created duration trend file: {duration_trend_file}", verbose)
    
    # Create categories trend if it doesn't exist
    if not categories_trend_file.exists():
        with open(categories_trend_file, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        log_message(f"Created categories trend file: {categories_trend_file}", verbose)
    
    # 7. Ensure history.json exists (required by Allure)
    if not history_file.exists():
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
        log_message(f"Created required history file: {history_file}", verbose)
    else:
        log_message(f"Verified required file exists: {history_file}", verbose)
    
    # 8. Final summary for clear logging in GitHub UI
    print("\n" + "="*70)
    print("ALLURE HISTORY MANAGEMENT SUMMARY")
    print("="*70)
    print(f"Status: {'HISTORY DOWNLOADED & CLEANED' if history_downloaded else 'FRESH START (No previous history)'}")
    print(f"New Build Order: {new_order}")
    print(f"Total Valid History Entries: {len(history_trend)}")
    print(f"Files in ./allure-results/history/:")
    for file in history_dir.iterdir():
        if file.is_file():
            print(f"   - {file.name} ({file.stat().st_size} bytes)")
    print("="*70)
    
    return new_order

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage and update Allure history files')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-s', '--silent', action='store_true', help='Enable silent mode (overrides verbose)')
    parser.add_argument('--clean', action='store_true', help='Clean invalid entries from existing history')
    parser.add_argument('--post-cleanup', action='store_true', help='Run post-Allure generation cleanup')
    
    args = parser.parse_args()
    verbose = args.verbose and not args.silent
    
    try:
        if args.post_cleanup:
            # Run post-generation cleanup
            entries_count = clean_post_allure_generation(verbose=verbose)
            log_message(f"Post-generation cleanup completed. {entries_count} entries processed.", verbose)
        else:
            # Run normal history management
            manage_allure_history(verbose=verbose)
            log_message("Allure history management completed successfully.", verbose)
        
        sys.exit(0)
    except Exception as e:
        log_message(f"CRITICAL ERROR: {e}", True)
        import traceback
        traceback.print_exc()
        sys.exit(1)