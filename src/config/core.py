"""
Unified configuration loader for both infrastructure and agent configs.

This module provides a unified approach to loading configuration files with:
- Support for both $VAR and ${VAR} environment variable formats
- Config file search paths: CWD → project root → ~/.ptc-agent/
- Caching to avoid repeated file reads
- Pydantic validation for infrastructure config

Config Files:
- config.yaml: Infrastructure settings (server, Redis, background tasks, logging, CORS)
- agent_config.yaml: Agent capabilities (LLM, MCP, tools, crawler, web_fetch, embedding, security)
"""

import logging
import os
import re
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.config.models import InfrastructureConfig

logger = logging.getLogger(__name__)


class ConfigContext(str, Enum):
    """Context for configuration loading behavior."""

    SDK = "sdk"  # CWD → git root → ~/.ptc-agent/
    CLI = "cli"  # ~/.ptc-agent/ → CWD (home first)

# =============================================================================
# Environment Variable Substitution
# =============================================================================


def substitute_env_vars(value: str) -> str:
    """
    Replace environment variables in string values.

    Supports both formats:
    - $VAR - Simple format
    - ${VAR} - Bash-style format with braces

    Args:
        value: String value potentially containing env var references

    Returns:
        String with environment variables substituted
    """
    if not isinstance(value, str):
        return value

    # Handle ${VAR} format first (bash style)
    pattern = r"\$\{([^}]+)\}"
    result = re.sub(
        pattern,
        lambda m: os.getenv(m.group(1), m.group(0)),  # Keep original if not found
        value,
    )

    # Handle $VAR format (simple)
    # Only match if the entire string is $VAR (legacy behavior)
    if result.startswith("$") and not result.startswith("${"):
        env_var = result[1:]
        # Only substitute if it looks like a simple variable name
        if env_var.isidentifier():
            return os.getenv(env_var, env_var)

    return result


def _process_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively process dictionary to replace environment variables."""
    if not config:
        return {}
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = _process_dict(value)
        elif isinstance(value, list):
            result[key] = _process_list(value)
        elif isinstance(value, str):
            result[key] = substitute_env_vars(value)
        else:
            result[key] = value
    return result


def _process_list(config_list: List[Any]) -> List[Any]:
    """Recursively process list to replace environment variables."""
    result = []
    for item in config_list:
        if isinstance(item, dict):
            result.append(_process_dict(item))
        elif isinstance(item, list):
            result.append(_process_list(item))
        elif isinstance(item, str):
            result.append(substitute_env_vars(item))
        else:
            result.append(item)
    return result


# =============================================================================
# Config File Search
# =============================================================================


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find git repository root by walking up from start_path.

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to project root if found, None otherwise
    """
    current = start_path or Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def get_default_config_dir() -> Path:
    """Get the default config directory (~/.ptc-agent/)."""
    return Path.home() / ".ptc-agent"


def ensure_config_dir() -> Path:
    """Ensure the default config directory exists."""
    config_dir = get_default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_search_paths(
    start_path: Optional[Path] = None,
    *,
    context: ConfigContext = ConfigContext.SDK,
) -> List[Path]:
    """
    Get ordered list of config search paths.

    Search order:
    - SDK: CWD → project root → ~/.ptc-agent/
    - CLI: ~/.ptc-agent/ → CWD

    Args:
        start_path: Starting directory (default: current working directory)
        context: Loading context (SDK or CLI)

    Returns:
        List of paths to search for config files
    """
    cwd = start_path or Path.cwd()
    home = get_default_config_dir()

    if context == ConfigContext.CLI:
        return [home, cwd]

    paths = [cwd]
    project_root = find_project_root(cwd)
    if project_root and project_root != cwd:
        paths.append(project_root)
    paths.append(home)
    return paths


def find_config_file(
    filename: str,
    search_paths: Optional[List[Path]] = None,
    env_var: Optional[str] = None,
    *,
    context: ConfigContext = ConfigContext.SDK,
) -> Optional[Path]:
    """
    Find first existing config file in search paths.

    Args:
        filename: Name of the file to find
        search_paths: Paths to search (default: get_config_search_paths())
        env_var: Environment variable to check for override
        context: Loading context for default search paths

    Returns:
        Path to the first existing file, or None if not found
    """
    # Check env var override first
    if env_var:
        env_path = os.getenv(env_var)
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path

    # Search paths in order
    if search_paths is None:
        search_paths = get_config_search_paths(context=context)

    for search_path in search_paths:
        candidate = search_path / filename
        if candidate.exists():
            return candidate

    return None


# =============================================================================
# YAML Loading with Caching
# =============================================================================

_config_cache: Dict[str, Dict[str, Any]] = {}


def load_yaml_config(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Load and process YAML configuration file.

    Args:
        file_path: Path to the YAML configuration file
        use_cache: Whether to use caching (default: True)

    Returns:
        Processed configuration dictionary with environment variables replaced
    """
    if not os.path.exists(file_path):
        logger.warning(f"Configuration file not found: {file_path}")
        return {}

    if use_cache and file_path in _config_cache:
        return _config_cache[file_path]

    with open(file_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    if not raw_config:
        logger.warning(f"Empty configuration file: {file_path}")
        return {}

    # Process environment variables in config values
    processed_config = _process_dict(raw_config)

    logger.debug(f"Loaded configuration from {file_path} (settings: {len(processed_config)})")

    if use_cache:
        _config_cache[file_path] = processed_config
    return processed_config


def clear_config_cache():
    """Clear the configuration cache. Useful for testing or when config files change."""
    global _config_cache
    _config_cache = {}
    # Also clear LRU caches
    load_infrastructure_config.cache_clear()
    logger.debug("Configuration cache cleared")


# =============================================================================
# Infrastructure Config Loading
# =============================================================================

# Config filenames
INFRASTRUCTURE_CONFIG_FILE = "config.yaml"
AGENT_CONFIG_FILE = "agent_config.yaml"


@lru_cache(maxsize=1)
def load_infrastructure_config(
    config_path: Optional[str] = None,
) -> InfrastructureConfig:
    """
    Load infrastructure configuration from config.yaml.

    This function is cached to avoid repeated file reads and validation.

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Validated InfrastructureConfig instance
    """
    if config_path:
        path = Path(config_path)
    else:
        path = find_config_file(INFRASTRUCTURE_CONFIG_FILE)

    if path is None:
        logger.warning("No infrastructure config file found, using defaults")
        return InfrastructureConfig()

    config_dict = load_yaml_config(str(path))
    return InfrastructureConfig(**config_dict)


def get_infrastructure_config() -> InfrastructureConfig:
    """
    Get the infrastructure configuration.

    Convenience function that calls load_infrastructure_config().

    Returns:
        InfrastructureConfig instance
    """
    return load_infrastructure_config()
