#!/usr/bin/env python3
"""
Configuration loader for wiki_test knowledge base.
Supports YAML config with environment variable substitution.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

# Try to import yaml, fallback to JSON if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    import json

# Default configuration (fallback if config.yaml not found)
DEFAULT_CONFIG = {
    'workspace': {
        'root': 'auto',
        'data_dir': './data'
    },
    'webdav': {
        'base_url': 'https://dav.jjb115799.fnos.net',
        'username': '',
        'password': '',
        'raw_path': '/下载/temp/wiki_raw/',
        'annotation_path': '/下载/temp/gemma_results/',
        'backup_path': '/下载/temp/'
    },
    'sources': {
        'raw': {'path': './raw'},
        'cards': {'path': './cards/sections', 'manifest': './cards/manifest.json'},
        'excel': {
            'root': './excel_store',
            'pricing': './excel_store/pricing',
            'comparison': './excel_store/comparison',
            'proposal': './excel_store/proposal'
        },
        'indexes': {
            'root': './index_store',
            'annotation': './index_store/annotation_doc_index.json',
            'fts5': './index_store/wiki_fts5.db'
        }
    },
    'query': {
        'default_limit': 20,
        'price_keywords': ['价格', '报价', '多少钱', '费用'],
        'compare_keywords': ['对比', '比较', '区别', '差异', 'vs'],
        'spec_keywords': ['规格', '接口', '编解码', '输入', '输出'],
        'accessory_keywords': ['配件', '附件', '可用配件'],
        'eol_keywords': ['停产', '替代', '退市']
    },
    'models': {
        'pattern': r'(AE\d{3}[A-Z]?|XE\d{3}[A-Z]?|GE\d{3}[A-Z]?|PE\d{4}|TP\d{3}(?:-[A-Z])?|MX\d{2}|AC\d{2}|NC\d{2}|NP\d{2}(?:V?\d+)?)'
    },
    'priority_docs': {
        'police': '24-行业应用口袋书-公安20220520.md',
        'software_hardware': '18-指挥中心采用软件客户端和硬件终端方案对比.md'
    }
}


class Config:
    """Configuration manager with environment variable support."""
    
    _instance = None
    
    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return
        self._initialized = True
        self._config = self._load_config(config_path)
        self._root = self._resolve_root()
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from YAML file or use defaults."""
        if config_path is None:
            # Try to find config.yaml in standard locations
            possible_paths = [
                Path(__file__).resolve().parents[1] / 'config.yaml',
                Path.cwd() / 'config.yaml',
                Path.cwd().parent / 'config.yaml'
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Substitute environment variables
                content = self._substitute_env_vars(content)
                
                if HAS_YAML:
                    config = yaml.safe_load(content)
                else:
                    # Fallback: try parsing as JSON-like
                    import json
                    config = json.loads(content)
                
                # Merge with defaults
                return self._merge_dicts(DEFAULT_CONFIG, config)
            except Exception as e:
                print(f"[WARN] Failed to load config from {config_path}: {e}")
                return DEFAULT_CONFIG
        
        return DEFAULT_CONFIG
    
    def _substitute_env_vars(self, content: str) -> str:
        """Substitute environment variables in format ${VAR:-default}."""
        def replace_var(match):
            var_expr = match.group(1)
            if ':-' in var_expr:
                var_name, default = var_expr.split(':-', 1)
                return os.environ.get(var_name, default)
            return os.environ.get(var_expr, '')
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, content)
    
    def _merge_dicts(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result
    
    def _resolve_root(self) -> Path:
        """Resolve knowledge base root directory."""
        root = self._config.get('workspace', {}).get('root', 'auto')
        
        if root == 'auto':
            # Auto-detect: try to find by looking for config.yaml
            script_dir = Path(__file__).resolve().parent
            for parent in [script_dir, script_dir.parent, script_dir.parents[1], Path.cwd()]:
                if (parent / 'config.yaml').exists():
                    return parent
            # Fallback to standard paths
            for path in [Path.cwd(), Path.cwd().parent, Path.home() / 'wiki_test']:
                if path.exists():
                    return path
        else:
            path = Path(root)
            if path.exists():
                return path.resolve()
        
        # Last resort: current working directory
        return Path.cwd()
    
    @property
    def root(self) -> Path:
        """Get knowledge base root directory."""
        return self._root
    
    def path(self, *keys: str) -> Path:
        """Get resolved path from config.
        
        Usage:
            config.path('sources', 'raw', 'path') -> Path to raw directory
            config.path('webdav', 'base_url') -> WebDAV URL
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                raise KeyError(f"Config path {'/'.join(keys)} not found")
        
        if isinstance(value, str) and not value.startswith('http'):
            # Resolve relative paths against root
            path = Path(value)
            if not path.is_absolute():
                return self._root / path
            return path
        return value
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """Get config value with optional default."""
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access: config['key']."""
        return self._config[key]
    
    def get_webdav_credentials(self) -> tuple:
        """Get WebDAV credentials from config or environment."""
        username = self.get('webdav', 'username', default='')
        password = self.get('webdav', 'password', default='')
        
        # Fallback to environment variables
        if not username:
            username = os.environ.get('WEBDAV_USER', '')
        if not password:
            password = os.environ.get('WEBDAV_PASS', '')
        
        return username, password
    
    def list_models(self) -> list:
        """Get list of configured model patterns."""
        return self.get('query', 'model_keywords', default=[])
    
    def get_priority_doc(self, doc_type: str) -> str:
        """Get priority document for specific type."""
        return self.get('priority_docs', doc_type, default='')


# Global config instance
config = Config()


def reload_config(path: Optional[str] = None) -> Config:
    """Reload configuration from file."""
    Config._instance = None
    return Config(path)


if __name__ == '__main__':
    # Test config loading
    cfg = Config()
    print(f"Root: {cfg.root}")
    print(f"Raw path: {cfg.path('sources', 'raw', 'path')}")
    print(f"Cards path: {cfg.path('sources', 'cards', 'path')}")
    print(f"WebDAV URL: {cfg.path('webdav', 'base_url')}")
