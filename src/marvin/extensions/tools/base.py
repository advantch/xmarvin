from inspect import signature
from typing import Any, Callable, Optional, Type

from pydantic import (
    BaseModel,
    create_model,
    validate_arguments,
)


class SchemaAnnotationError(TypeError):
    """Raised when 'args_schema' is missing or has an incorrect type annotation."""


def _create_subset_model(
    name: str, model: Type[BaseModel], field_names: list
) -> Type[BaseModel]:
    """Create a pydantic model with only a subset of model's fields."""
    fields = {}
    for field_name in field_names:
        field = model.model_fields[field_name]
        annotation = field.annotation
        if hasattr(annotation, "__args__"):
            annotation = annotation.__args__[0]
        t = (
            # this isn't perfect but should work for most functions
            annotation if field.is_required else Optional[annotation]
        )
        fields[field_name] = (t, field)
    rtn = create_model(name, **fields)  # type: ignore
    return rtn


def _get_filtered_args(
    inferred_model: Type[BaseModel],
    func: Callable,
) -> dict:
    """Get the arguments from a function's signature."""
    schema = inferred_model.model_json_schema()["properties"]
    valid_keys = signature(func).parameters
    return {k: schema[k] for k in valid_keys if k not in ("run_manager", "callbacks")}


class _SchemaConfig:
    """Configuration for the pydantic model."""

    extra: Any = "forbid"
    arbitrary_types_allowed: bool = True


def create_schema_from_function(
    model_name: str,
    func: Callable,
) -> Type[BaseModel]:
    """Create a pydantic schema from a function's signature.
    Args:
        model_name: Name to assign to the generated pydandic schema
        func: Function to generate the schema from
    Returns:
        A pydantic model with the same arguments as the function
    """
    # https://docs.pydantic.dev/latest/usage/validation_decorator/
    validated = validate_arguments(func, config=_SchemaConfig)  # type: ignore
    inferred_model = validated.model  # type: ignore
    if "run_manager" in inferred_model.__fields__:
        del inferred_model.__fields__["run_manager"]
    if "callbacks" in inferred_model.__fields__:
        del inferred_model.__fields__["callbacks"]
    # Pydantic adds placeholder virtual fields we need to strip
    valid_properties = _get_filtered_args(inferred_model, func)
    return _create_subset_model(
        f"{model_name}Schema", inferred_model, list(valid_properties)
    )


class ToolException(Exception):
    """Optional exception that tool throws when execution error occurs.

    When this exception is thrown, the agent will not stop working,
    but it will handle the exception according to the handle_tool_error
    variable of the tool, and the processing result will be returned
    to the agent as observation, and printed in red on the console.
    """

    pass
