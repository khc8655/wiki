#!/usr/bin/env python3
"""
wiki_test Knowledge Base Setup Script

Run this script to initialize and validate the knowledge base environment.

Usage:
    python setup.py              # Interactive setup
    python setup.py --check     # Validate existing setup
    python setup.py --init      # Initialize directories
    python setup.py --env       # Print environment variables needed
"""

import argparse
import os
import sys
from pathlib import Path

# Add lib to path
LIB_DIR = Path(__file__).resolve().parent / 'lib'
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from config import Config, config


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print('=' * 60)


def print_check(name: str, status: bool, message: str = ""):
    """Print check result."""
    symbol = "✓" if status else "✗"
    color = "\033[92m" if status else "\033[91m"  # Green/Red
    reset = "\033[0m"
    print(f"  {color}[{symbol}]{reset} {name:<40} {message}")


def check_directory_structure():
    """Check if required directories exist."""
    print_header("Directory Structure Check")
    
    required_dirs = [
        ('Raw source', config.path('sources', 'raw', 'path')),
        ('Cards', config.path('sources', 'cards', 'path')),
        ('Excel root', config.path('sources', 'excel', 'root')),
        ('Excel pricing', config.path('sources', 'excel', 'pricing')),
        ('Excel comparison', config.path('sources', 'excel', 'comparison')),
        ('Excel proposal', config.path('sources', 'excel', 'proposal')),
        ('Indexes', config.path('sources', 'indexes', 'root')),
    ]
    
    all_exist = True
    for name, path in required_dirs:
        exists = path.exists()
        print_check(name, exists, str(path))
        if not exists:
            all_exist = False
    
    return all_exist


def check_excel_data():
    """Check if Excel data is available."""
    print_header("Excel Data Check")
    
    excel_types = ['pricing', 'comparison', 'proposal']
    all_ok = True
    
    for dtype in excel_types:
        records_file = config.path('sources', 'excel', dtype) / 'records.json'
        indexes_file = config.path('sources', 'excel', dtype) / 'indexes.json'
        
        exists = records_file.exists() and indexes_file.exists()
        count = 0
        if records_file.exists():
            try:
                import json
                count = len(json.loads(records_file.read_text()))
            except:
                pass
        
        print_check(f"{dtype} data", exists, f"{count} records" if exists else "missing")
        if not exists:
            all_ok = False
    
    return all_ok


def check_card_data():
    """Check if card data is available."""
    print_header("Card Data Check")
    
    cards_dir = config.path('sources', 'cards', 'path')
    if not cards_dir.exists():
        print_check("Cards directory", False, "Not found")
        return False
    
    card_files = list(cards_dir.glob('*.json'))
    count = len(card_files)
    
    print_check("Cards directory", True, f"{count} cards")
    
    # Check if semantic metadata exists
    semantic_count = 0
    sample_cards = card_files[:10]
    for card_file in sample_cards:
        try:
            import json
            card = json.loads(card_file.read_text())
            if 'semantic' in card:
                semantic_count += 1
        except:
            pass
    
    if semantic_count > 0:
        print_check("Semantic metadata", True, f"{semantic_count}/{len(sample_cards)} sampled")
    else:
        print_check("Semantic metadata", False, "Not found (run merge)")
    
    return count > 0


def check_webdav_config():
    """Check WebDAV configuration."""
    print_header("WebDAV Configuration Check")
    
    base_url = config.path('webdav', 'base_url')
    username, password = config.get_webdav_credentials()
    
    print_check("Base URL", True, base_url)
    print_check("Username", bool(username), username or "(not set)")
    print_check("Password", bool(password), "***" if password else "(not set)")
    
    return bool(username and password)


def check_scripts():
    """Check if required scripts exist."""
    print_header("Scripts Check")
    
    scripts_dir = config.root / 'scripts'
    required_scripts = [
        'query_fast.py',
        'run_fast_tests.py',
        'benchmark_fast_queries.py',
        'import_webdav_raw.py',
        'merge_annotations_to_cards.py',
        'refresh_from_webdav.sh',
    ]
    
    all_exist = True
    for script in required_scripts:
        path = scripts_dir / script
        exists = path.exists()
        print_check(script, exists)
        if not exists:
            all_exist = False
    
    return all_exist


def print_environment_help():
    """Print environment variable help."""
    print_header("Environment Variables")
    
    print("""
The following environment variables can override config.yaml:

  WEBDAV_USER        WebDAV username
  WEBDAV_PASS        WebDAV password
  WEBDAV_URL         WebDAV base URL (default: https://dav.jjb115799.fnos.net)
  
  WIKI_ROOT          Knowledge base root directory (default: auto-detect)
  WIKI_DATA_DIR      Data storage directory (default: ./data)
  
  LOG_LEVEL          Logging level (default: INFO)

Examples:
  export WEBDAV_USER="your_username"
  export WEBDAV_PASS="your_password"
  
  # Or one-time
  WEBDAV_USER="user" WEBDAV_PASS="pass" python scripts/query_fast.py "query"
""")


def initialize_directories():
    """Initialize required directories."""
    print_header("Initializing Directories")
    
    dirs_to_create = [
        config.path('sources', 'raw', 'path'),
        config.path('sources', 'cards', 'path'),
        config.path('sources', 'excel', 'root'),
        config.path('sources', 'excel', 'pricing'),
        config.path('sources', 'excel', 'comparison'),
        config.path('sources', 'excel', 'proposal'),
        config.path('sources', 'indexes', 'root'),
        config.root / 'logs',
    ]
    
    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {dir_path}")
    
    print("\n✓ Directories initialized")


def print_quickstart():
    """Print quickstart guide."""
    print_header("Quick Start Guide")
    
    print("""
1. Set WebDAV credentials (if syncing from WebDAV):
   export WEBDAV_USER="your_username"
   export WEBDAV_PASS="your_password"

2. Import data from WebDAV:
   ./scripts/refresh_from_webdav.sh
   
   Or manually place files:
   - Raw docs: ./raw/
   - Excel data: ./excel_store/{pricing,comparison,proposal}/

3. Build Excel indexes:
   python scripts/build_excel_knowledge.py

4. Merge annotations (if available):
   python scripts/merge_annotations_to_cards.py

5. Test queries:
   python scripts/run_fast_tests.py
   
   Or single query:
   python scripts/query_fast.py "AE800多少钱"

6. Benchmark:
   python scripts/benchmark_fast_queries.py

For help with specific scripts:
   python scripts/query_fast.py --help
""")


def main():
    parser = argparse.ArgumentParser(
        description='wiki_test Knowledge Base Setup',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s              # Full setup check
  %(prog)s --check      # Validate existing setup
  %(prog)s --init       # Initialize directories
  %(prog)s --env        # Show environment variables
        """
    )
    parser.add_argument('--check', action='store_true', help='Validate existing setup')
    parser.add_argument('--init', action='store_true', help='Initialize directories')
    parser.add_argument('--env', action='store_true', help='Show environment variables')
    parser.add_argument('--quickstart', action='store_true', help='Show quickstart guide')
    args = parser.parse_args()
    
    if args.env:
        print_environment_help()
        return
    
    if args.quickstart:
        print_quickstart()
        return
    
    if args.init:
        initialize_directories()
        return
    
    # Default: full check
    print_header("wiki_test Knowledge Base Setup Check")
    print(f"Root directory: {config.root}")
    print()
    
    checks = [
        ("Directory Structure", check_directory_structure),
        ("Excel Data", check_excel_data),
        ("Card Data", check_card_data),
        ("WebDAV Config", check_webdav_config),
        ("Scripts", check_scripts),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            results.append((name, False))
    
    print_header("Summary")
    all_passed = all(r[1] for r in results)
    for name, passed in results:
        print_check(name, passed, "OK" if passed else "Needs attention")
    
    print()
    if all_passed:
        print("✓ Setup is complete and ready to use!")
        print("\nRun 'python setup.py --quickstart' for usage guide.")
    else:
        print("✗ Some checks failed. Run 'python setup.py --init' to create missing directories.")
        print("  Run 'python setup.py --env' for WebDAV configuration help.")


if __name__ == '__main__':
    main()