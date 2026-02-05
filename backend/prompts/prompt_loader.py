"""
Prompt Loader

Utility for loading prompt templates from files.

Prompts are stored in backend/prompts/ directory and can include
variables using {variable} syntax for template substitution.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Default prompts directory
PROMPTS_DIR = Path(__file__).parent


def load_prompt(
    prompt_name: str,
    prompts_dir: Optional[Path] = None
) -> str:
    """
    Load a prompt from a file

    Args:
        prompt_name: Name of the prompt file (without extension)
                    e.g., "data_manager_system" loads "data_manager_system.txt"
        prompts_dir: Optional custom prompts directory.
                     Defaults to backend/prompts/

    Returns:
        Prompt content as string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        IOError: If prompt file cannot be read

    Example:
        >>> prompt = load_prompt("data_manager_system")
        >>> print(prompt)
    """
    if prompts_dir is None:
        prompts_dir = PROMPTS_DIR

    # Try .txt extension first, then .md
    prompt_file = prompts_dir / f"{prompt_name}.txt"
    if not prompt_file.exists():
        prompt_file = prompts_dir / f"{prompt_name}.md"

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_name} "
            f"(searched in {prompts_dir})"
        )

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            content = f.read()

        logger.debug(f"Loaded prompt from {prompt_file}")
        return content

    except Exception as e:
        logger.error(f"Error reading prompt file {prompt_file}: {e}")
        raise


def load_prompt_template(
    prompt_name: str,
    variables: Dict[str, Any],
    prompts_dir: Optional[Path] = None
) -> str:
    """
    Load a prompt template and substitute variables

    Args:
        prompt_name: Name of the prompt file
        variables: Dictionary of variables to substitute in the template
                    e.g., {"model_name": "gpt-4", "max_tokens": 2000}
        prompts_dir: Optional custom prompts directory

    Returns:
        Prompt with variables substituted

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        KeyError: If required variable is missing

    Example:
        >>> prompt = load_prompt_template(
        ...     "agent_prompt",
        ...     variables={"name": "DrHyper", "version": "1.0"}
        ... )
        >>> print(prompt)
    """
    template = load_prompt(prompt_name, prompts_dir)

    try:
        return template.format(**variables)
    except KeyError as e:
        missing_var = e.args[0] if e.args else "unknown"
        raise KeyError(
            f"Missing required variable '{missing_var}' in prompt template '{prompt_name}'"
        )


def list_available_prompts(prompts_dir: Optional[Path] = None) -> list[str]:
    """
    List all available prompt files

    Args:
        prompts_dir: Optional custom prompts directory

    Returns:
        List of prompt names (without extension)

    Example:
        >>> prompts = list_available_prompts()
        >>> print(prompts)  # ['data_manager_system', 'drhyper_agent', ...]
    """
    if prompts_dir is None:
        prompts_dir = PROMPTS_DIR

    prompt_files = []

    for file_path in prompts_dir.iterdir():
        if file_path.is_file() and file_path.suffix in [".txt", ".md"]:
            # Remove extension
            prompt_name = file_path.stem
            prompt_files.append(prompt_name)

    return sorted(prompt_files)


def prompt_exists(prompt_name: str, prompts_dir: Optional[Path] = None) -> bool:
    """
    Check if a prompt file exists

    Args:
        prompt_name: Name of the prompt file (without extension)
        prompts_dir: Optional custom prompts directory

    Returns:
        True if prompt file exists, False otherwise

    Example:
        >>> if prompt_exists("data_manager_system"):
        ...     prompt = load_prompt("data_manager_system")
    """
    if prompts_dir is None:
        prompts_dir = PROMPTS_DIR

    # Try both extensions
    txt_file = prompts_dir / f"{prompt_name}.txt"
    md_file = prompts_dir / f"{prompt_name}.md"

    return txt_file.exists() or md_file.exists()
