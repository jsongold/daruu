"""Prompt variations for label linking experiments.

This module provides different prompt versions that can be tested
against each other to find the optimal label linking prompts.
"""

from typing import Protocol


class PromptSet(Protocol):
    """Protocol for a set of prompts used in label linking."""

    name: str
    description: str
    system_prompt: str
    user_prompt_template: str


def get_available_prompts() -> list[str]:
    """Get list of available prompt version names."""
    return ["default", "v2"]


def get_prompt_set(name: str) -> "PromptSet":
    """Get a prompt set by name.

    Args:
        name: Name of the prompt set (e.g., "default", "v2")

    Returns:
        PromptSet with system and user prompts

    Raises:
        ValueError: If prompt set not found
    """
    if name == "default":
        from . import default
        return default
    elif name == "v2":
        from . import v2
        return v2
    else:
        raise ValueError(f"Unknown prompt set: {name}. Available: {get_available_prompts()}")
