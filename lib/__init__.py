#!/usr/bin/env python3
"""
wiki_test library modules.

Usage:
    from lib.config import config
    
    # Get paths
    raw_path = config.path('sources', 'raw', 'path')
    
    # Get credentials
    username, password = config.get_webdav_credentials()
"""

from .config import Config, config, reload_config

__all__ = ['Config', 'config', 'reload_config']
