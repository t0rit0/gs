"""
Prompts Module

Manages system prompts for various AI agents.
Prompts are stored as separate files for easy management and version control.
"""
from backend.prompts.prompt_loader import load_prompt, load_prompt_template

__all__ = ["load_prompt", "load_prompt_template"]
