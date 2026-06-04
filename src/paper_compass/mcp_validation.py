"""Validation helpers for MCP tool arguments."""

from __future__ import annotations

from typing import Any, Dict, List

from paper_compass.mcp_contracts import accepted_params, get_tool_contract, param_schema, required_params


_TYPE_NAMES = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def validate_tool_arguments(tool_name: str, params: Dict[str, Any]) -> List[str]:
    contract = get_tool_contract(tool_name)
    if contract is None:
        return []

    schema = contract.get("inputSchema", {})
    errors: List[str] = []
    allowed = set(accepted_params(tool_name))
    unknown_params = sorted(k for k in params.keys() if k not in allowed)
    if unknown_params:
        errors.append(
            f"Unsupported parameters: {', '.join(unknown_params)}. Allowed parameters: {', '.join(sorted(allowed))}"
        )

    missing_required = [param for param in required_params(tool_name) if param not in params]
    if missing_required:
        errors.append(f"Missing required parameters: {', '.join(missing_required)}")

    if tool_name == "get_paper_metadata":
        has_handle = bool(params.get("paper_handle"))
        has_id = bool(params.get("id_or_doi"))
        if has_handle == has_id:
            errors.append("Exactly one of 'paper_handle' or 'id_or_doi' is required")

    for key, value in params.items():
        prop_schema = param_schema(tool_name, key)
        if prop_schema is None:
            continue
        errors.extend(_validate_value(f"{key}", value, prop_schema))

    return errors


def _validate_value(path: str, value: Any, schema: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    expected_type = schema.get("type")
    if expected_type:
        py_type = _TYPE_NAMES.get(expected_type)
        if py_type is not None and not isinstance(value, py_type):
            errors.append(
                f"Invalid parameter '{path}': expected {expected_type}, got {type(value).__name__}"
            )
            return errors

    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        errors.append(
            f"Invalid parameter '{path}': expected one of {enum_values}, got {value!r}"
        )

    if expected_type == "array":
        item_schema = schema.get("items", {})
        for idx, item in enumerate(value):
            errors.extend(_validate_value(f"{path}[{idx}]", item, item_schema))

    if expected_type == "object":
        properties = schema.get("properties", {})
        additional_allowed = schema.get("additionalProperties", True)
        if not additional_allowed:
            unknown_keys = sorted(k for k in value.keys() if k not in properties)
            if unknown_keys:
                errors.append(
                    f"Invalid parameter '{path}': unsupported keys {', '.join(unknown_keys)}"
                )
        for subkey, subvalue in value.items():
            subschema = properties.get(subkey)
            if subschema is None:
                continue
            errors.extend(_validate_value(f"{path}.{subkey}", subvalue, subschema))

    return errors
