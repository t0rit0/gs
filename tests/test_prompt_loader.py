"""
Tests for Prompt Loader

Tests cover:
1. Loading prompts from files
2. Loading prompt templates with variables
3. Listing available prompts
4. Checking if prompts exist
5. Error handling
"""

import pytest
import tempfile
from pathlib import Path

from backend.prompts.prompt_loader import (
    load_prompt,
    load_prompt_template,
    list_available_prompts,
    prompt_exists
)


class TestLoadPrompt:
    """Test suite for load_prompt function"""

    def test_load_existing_prompt(self):
        """
        Test loading an existing prompt file

        Given: An existing prompt file
        When: Loading the prompt
        Then: Should return the file content
        """
        # The data_manager_system.txt prompt should exist
        content = load_prompt("data_manager_system")

        assert isinstance(content, str)
        assert len(content) > 0
        # Check for some known content
        assert "database operations assistant" in content.lower()

    def test_load_prompt_with_txt_extension(self):
        """Test that .txt extension is found automatically"""
        content = load_prompt("data_manager_system")
        assert content is not None
        assert len(content) > 0

    def test_load_nonexistent_prompt_raises_error(self):
        """
        Test that loading non-existent prompt raises FileNotFoundError

        Given: A prompt that doesn't exist
        When: Trying to load it
        Then: Should raise FileNotFoundError
        """
        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            load_prompt("nonexistent_prompt_xyz")

    def test_load_prompt_from_custom_directory(self):
        """
        Test loading prompt from custom directory

        Given: A custom prompts directory with a prompt file
        When: Loading from that directory
        Then: Should load from custom directory
        """
        # Create temporary directory with prompt
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            prompt_file = tmpdir / "custom_prompt.txt"
            prompt_file.write_text("Custom prompt content")

            # Load from custom directory
            content = load_prompt("custom_prompt", prompts_dir=tmpdir)

            assert content == "Custom prompt content"


class TestLoadPromptTemplate:
    """Test suite for load_prompt_template function"""

    def test_load_template_with_variables(self):
        """
        Test loading template and substituting variables

        Given: A template with variables
        When: Loading with variable values
        Then: Should substitute variables correctly
        """
        # Create temporary template
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            template_file = tmpdir / "test_template.txt"
            template_file.write_text(
                "Hello {name}, you are using {model} model."
            )

            # Load with variables
            content = load_prompt_template(
                "test_template",
                variables={"name": "Alice", "model": "GPT-4"},
                prompts_dir=tmpdir
            )

            assert content == "Hello Alice, you are using GPT-4 model."

    def test_load_template_missing_variable_raises_error(self):
        """
        Test that missing variable raises KeyError

        Given: A template with variables
        When: Loading without all required variables
        Then: Should raise KeyError
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            template_file = tmpdir / "incomplete.txt"
            template_file.write_text("Hello {name}, from {city}")

            with pytest.raises(KeyError, match="Missing required variable"):
                load_prompt_template(
                    "incomplete",
                    variables={"name": "Bob"},  # Missing 'city'
                    prompts_dir=tmpdir
                )


class TestListAvailablePrompts:
    """Test suite for list_available_prompts function"""

    def test_list_prompts_returns_list(self):
        """
        Test that list_available_prompts returns a list

        Given: Prompts directory exists
        When: Listing prompts
        Then: Should return a list of prompt names
        """
        prompts = list_available_prompts()

        assert isinstance(prompts, list)
        assert len(prompts) > 0
        # Should contain our data_manager_system prompt
        assert "data_manager_system" in prompts

    def test_list_prompts_from_custom_directory(self):
        """
        Test listing prompts from custom directory

        Given: Custom directory with prompt files
        When: Listing prompts from that directory
        Then: Should return only prompts from that directory
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "prompt1.txt").write_text("content1")
            (tmpdir / "prompt2.md").write_text("content2")
            (tmpdir / "readme.txt").write_text("not a prompt")  # Still counted

            prompts = list_available_prompts(prompts_dir=tmpdir)

            assert len(prompts) == 3
            assert "prompt1" in prompts
            assert "prompt2" in prompts
            assert "readme" in prompts

    def test_list_prompts_sorted_alphabetically(self):
        """Test that prompts are sorted alphabetically"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "z_prompt.txt").write_text("z")
            (tmpdir / "a_prompt.txt").write_text("a")
            (tmpdir / "m_prompt.txt").write_text("m")

            prompts = list_available_prompts(prompts_dir=tmpdir)

            assert prompts == ["a_prompt", "m_prompt", "z_prompt"]


class TestPromptExists:
    """Test suite for prompt_exists function"""

    def test_prompt_exists_returns_true_for_existing(self):
        """
        Test that prompt_exists returns True for existing prompts

        Given: An existing prompt file
        When: Checking if it exists
        Then: Should return True
        """
        assert prompt_exists("data_manager_system") is True

    def test_prompt_exists_returns_false_for_nonexistent(self):
        """
        Test that prompt_exists returns False for non-existent prompts

        Given: A prompt that doesn't exist
        When: Checking if it exists
        Then: Should return False
        """
        assert prompt_exists("nonexistent_prompt_xyz") is False

    def test_prompt_exists_with_custom_directory(self):
        """
        Test prompt_exists with custom directory

        Given: Custom directory with specific prompts
        When: Checking existence in that directory
        Then: Should check in custom directory
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "exists.txt").write_text("content")

            assert prompt_exists("exists", prompts_dir=tmpdir) is True
            assert prompt_exists("not_exists", prompts_dir=tmpdir) is False
