"""
ORM Helper Functions for DataManager

This module provides utilities to dynamically extract ORM model information
and generate documentation for the CodeAgent's system prompt.

Everything is generated dynamically from the actual ORM models and CRUD classes.
"""

from typing import Dict, List, Any, Type, Optional, Set
from sqlalchemy import inspect
from sqlalchemy.orm import Mapper
from sqlalchemy.ext.declarative import DeclarativeMeta

from backend.database.base import Base
from backend.database.models import get_all_models
from backend.database import crud
from backend.config.config_manager import get_config



def _get_data_manager_config() -> Dict[str, Any]:
    """
    Load DataManager configuration from config file
    """
    try:
        config = get_config()

        # Get blocked tables (default: conversations, messages)
        blocked_tables = config.get("data_manager.blocked_tables", ["conversations", "messages"])

        # Get read-only tables (default: empty)
        read_only_tables = config.get("data_manager.read_only_tables", [])

        # Get model descriptions (default: empty dict - will use class docstrings)
        model_descriptions = config.get("data_manager.model_descriptions", {})

        return {
            "blocked_tables": set(blocked_tables) if blocked_tables else set(),
            "read_only_tables": set(read_only_tables) if read_only_tables else set(),
            "model_descriptions": model_descriptions if model_descriptions else {},
        }
    except Exception as e:
        # Fallback to defaults if config loading fails
        import logging
        logging.warning(f"Failed to load DataManager config: {e}. Using defaults.")
        return {
            "blocked_tables": {"conversations", "messages"},
            "read_only_tables": set(),
            "model_descriptions": {},
        }


# Load configuration at module import
_data_manager_config = _get_data_manager_config()
BLOCKED_TABLES: Set[str] = _data_manager_config["blocked_tables"]
READ_ONLY_TABLES: Set[str] = _data_manager_config["read_only_tables"]
_MODEL_DESCRIPTION_OVERRIDES: Dict[str, str] = _data_manager_config["model_descriptions"]


def get_model_description(model_class) -> str:
    """
    Get description for a model class

    Priority:
    1. Config override (model_descriptions in config.yaml)
    2. Class docstring (first meaningful line)
    3. Default generated description

    Args:
        model_class: SQLAlchemy model class

    Returns:
        Description string
    """
    table_name = model_class.__tablename__

    # 1. Check config overrides first
    if table_name in _MODEL_DESCRIPTION_OVERRIDES:
        return _MODEL_DESCRIPTION_OVERRIDES[table_name]

    # 2. Try to extract from class docstring
    if hasattr(model_class, "__doc__") and model_class.__doc__:
        doc = model_class.__doc__.strip()

        # Skip SQLAlchemy-generated docstrings
        if doc and not doc.startswith("SQLAlchemy") and len(doc) > 10:
            # Extract first meaningful line (skip empty lines)
            lines = [line.strip() for line in doc.split("\n") if line.strip()]
            if lines:
                # Return first line, but clean up any trailing periods
                first_line = lines[0].rstrip(".")
                return first_line

    # 3. Fallback to generated description
    class_name = model_class.__name__
    # Convert CamelCase to readable format
    import re
    readable_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', class_name)
    return f"{readable_name} Model"


def get_crud_instance_name(model_class) -> str:
    """
    Get the CRUD instance variable name for a model

    Args:
        model_class: SQLAlchemy model class

    Returns:
        Name of the CRUD instance variable (e.g., "patient_crud")
    """
    model_name = model_class.__name__
    # Convert Patient -> patient_crud, Conversation -> conversation_crud
    return f"{model_name.lower()}_crud"

def get_model_field_info(model_class) -> Dict[str, str]:
    """
    Extract field information from a SQLAlchemy model

    Args:
        model_class: SQLAlchemy model class

    Returns:
        Dictionary mapping field names to their types
    """
    mapper = inspect(model_class)
    fields = {}

    for column in mapper.columns:
        field_name = column.name
        field_type = str(column.type)

        # Add nullability info
        if column.nullable:
            field_type += " (nullable)"

        # Add primary key info
        if column.primary_key:
            field_type += " (PRIMARY KEY)"

        # Add default info (clean up CallableColumnDefault)
        if column.default is not None:
            default_str = str(column.default)
            # Clean up verbose default strings
            if "CallableColumnDefault" in default_str:
                field_type += " (default: auto)"
            else:
                field_type += f" (default: {default_str})"

        fields[field_name] = field_type

    return fields


# ============================================
# Documentation Generation
# ============================================

def generate_orm_documentation() -> str:
    """
    Generate simplified ORM documentation for the CodeAgent

    Only provides table structures. Agent uses introspection to discover CRUD methods.

    Returns:
        Formatted string with ORM models and field information
    """
    # Dynamically discover all models
    models = get_all_models()

    doc_lines = []

    # Find first writable model for introspection example
    example_crud_name = None
    for model_class in models:
        if model_class.__tablename__ not in BLOCKED_TABLES:
            example_crud_name = get_crud_instance_name(model_class)
            break

    if example_crud_name:
        doc_lines.extend([
            f"## Quick Example: Query a record",
            "",
            "```python",
            f"db = SessionLocal()",
            f"# Explore available methods",
            f"print(dir({example_crud_name}))",
            f"#",
            f"# Get a record by ID",
            f"result = {example_crud_name}.get(db, 'some-id')",
            f"print(result)",
            f"db.close()",
            "```",
            "",
        ])

    doc_lines.extend(["## Table Structures:", ""])

    # Document each model's structure only
    for model_class in models:
        table_name = model_class.__tablename__
        class_name = model_class.__name__
        description = get_model_description(model_class)

        # Determine access level
        if table_name in BLOCKED_TABLES:
            access_level = "🚫 BLOCKED"
            access_note = "DO NOT access this table"
        elif table_name in READ_ONLY_TABLES:
            access_level = "👁️ READ-ONLY"
            access_note = "Query only, no modifications"
        else:
            access_level = "✅ FULL ACCESS"
            access_note = "All operations available"

        crud_name = get_crud_instance_name(model_class)

        doc_lines.extend([
            f"### {class_name} - {description}",
            f"",
            f"**Table:** `{table_name}`",
            f"**CRUD object:** `{crud_name}`",
            f"**Access:** {access_level} - {access_note}",
            "",
            "**Fields:**",
        ])

        # Get field information
        fields = get_model_field_info(model_class)
        for field_name, field_type in fields.items():
            doc_lines.append(f"  - `{field_name}`: {field_type}")

        doc_lines.append("")

    # Add security note
    blocked_list = ", ".join(f"`{t}`" for t in BLOCKED_TABLES)
    doc_lines.extend([
        "-" * 60,
        "",
        f"**Security:** {blocked_list} tables are blocked and cannot be accessed.",
        "",
    ])

    return "\n".join(doc_lines)


def get_table_structures() -> str:
    """
    Generate table structures for template substitution

    Returns only the dynamic table structure information.
    This is designed to be inserted into the {TABLE_STRUCTURES} placeholder
    in the prompt template.

    Returns:
        String with table structures
    """
    models = get_all_models()

    doc_lines = ["## Table Structures", ""]

    # Document each model's structure
    for model_class in models:
        table_name = model_class.__tablename__
        class_name = model_class.__name__
        description = get_model_description(model_class)

        # Determine access level
        if table_name in BLOCKED_TABLES:
            access_level = "🚫 BLOCKED"
            access_note = "DO NOT access this table"
        elif table_name in READ_ONLY_TABLES:
            access_level = "👁️ READ-ONLY"
            access_note = "Query only, no modifications"
        else:
            access_level = "✅ FULL ACCESS"
            access_note = "All operations available"

        crud_name = get_crud_instance_name(model_class)

        doc_lines.extend([
            f"### {class_name}",
            "",
            f"**Table:** `{table_name}`",
            f"**CRUD object:** `{crud_name}`",
            f"**Access:** {access_level} - {access_note}",
            "",
            "**Fields:**",
        ])

        # Get field information
        fields = get_model_field_info(model_class)
        for field_name, field_type in fields.items():
            doc_lines.append(f"  - `{field_name}`: {field_type}")

        doc_lines.append("")

    # Add security note
    blocked_list = ", ".join(f"`{t}`" for t in BLOCKED_TABLES)
    doc_lines.extend([
        "-" * 60,
        "",
        f"**Security:** {blocked_list} tables are blocked and cannot be accessed.",
    ])

    return "\n".join(doc_lines)


def get_custom_instructions() -> str:
    """
    Get custom instructions by loading template and substituting table structures

    This loads the prompt template and substitutes {TABLE_STRUCTURES} placeholder.

    Returns:
        String with custom instructions (template with table structures)
    """
    from pathlib import Path

    # Load template
    template_path = Path(__file__).parent.parent / "prompts" / "data_manager_system.txt"

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        # Fallback if template not found
        return generate_orm_documentation()

    # Generate table structures
    table_structures = get_table_structures()

    # Substitute placeholder
    return template.replace("{TABLE_STRUCTURES}", table_structures)


# Convenience function for quick testing
if __name__ == "__main__":
    print("=" * 80)
    print("Dynamic ORM Documentation Preview")
    print("=" * 80)
    print()
    print(get_custom_instructions())
