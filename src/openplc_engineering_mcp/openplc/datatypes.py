"""OpenPLC project-defined data type inspection."""

import re
from typing import Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import load_project_document, list_source_files


class StructureField(TypedDict):
    name: str
    type: str
    initial_value: str | None
    documentation: str | None


class EnumeratedDataTypeInfo(TypedDict):
    name: str
    kind: Literal["enumerated"]
    values: list[str]
    initial_value: str | None


class StructureDataTypeInfo(TypedDict):
    name: str
    kind: Literal["structure"]
    fields: list[StructureField]


class ArrayDataTypeInfo(TypedDict):
    name: str
    kind: Literal["array"]
    base_type: str
    dimensions: list[str]
    initial_value: str | None


DataTypeInfo = EnumeratedDataTypeInfo | StructureDataTypeInfo | ArrayDataTypeInfo

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_QUALIFIED_IDENTIFIER = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*"
_STRUCT_START_RE = re.compile(rf"^(?P<name>{_IDENTIFIER})\s*:\s*STRUCT$", re.IGNORECASE)
_STRUCT_END_RE = re.compile(r"^END_STRUCT\s*;$", re.IGNORECASE)
_ENUM_RE = re.compile(
    rf"^(?P<name>{_IDENTIFIER})\s*:\s*\((?P<values>[^)]*)\)\s*"
    r"(?::=\s*(?P<initial>[^;]+?))?\s*;$"
)
_ARRAY_RE = re.compile(
    rf"^(?P<name>{_IDENTIFIER})\s*:\s*ARRAY\s*\[(?P<dimensions>[^\]]+)\]\s+OF\s+"
    rf"(?P<base>{_QUALIFIED_IDENTIFIER})\s*(?::=\s*(?P<initial>[^;]+?))?\s*;$",
    re.IGNORECASE,
)
_ARRAY_TYPE_RE = re.compile(
    rf"^ARRAY\s*\[(?P<dimensions>[^\]]+)\]\s+OF\s+(?P<base>{_QUALIFIED_IDENTIFIER})$",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(
    rf"^(?P<name>{_IDENTIFIER})\s*:\s*(?P<type>[\w\s\[\],.]+?)\s*"
    r"(?::=\s*(?P<initial>[^;]+?))?\s*;\s*"
    r"(?:\(\*\s*(?P<documentation>.*?)\s*\*\))?$",
    re.IGNORECASE,
)


def _optional_text(value: object, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f'legacy data type field "{field}" must be a string or null')
    stripped = value.strip()
    return stripped or None


def _dimensions(value: str) -> list[str]:
    dimensions = [dimension.strip() for dimension in value.split(",")]
    if any(not dimension for dimension in dimensions):
        raise ValueError("array dimensions must not be empty")
    return dimensions


def _declared_type(value: str) -> str:
    declared_type = value.strip()
    array = _ARRAY_TYPE_RE.fullmatch(declared_type)
    if array:
        _dimensions(array.group("dimensions"))
        return declared_type
    if re.fullmatch(_QUALIFIED_IDENTIFIER, declared_type):
        return declared_type
    raise ValueError(f'unsupported declared type "{declared_type}"')


def _parse_dt(content: str, expected_name: str) -> DataTypeInfo:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty file - expected a TYPE...END_TYPE declaration")
    if not re.fullmatch(r"TYPE", lines[0], re.IGNORECASE):
        raise ValueError("declaration must start with TYPE")
    if not re.fullmatch(r"END_TYPE", lines[-1], re.IGNORECASE):
        raise ValueError("declaration must end with END_TYPE")

    body = lines[1:-1]
    if not body:
        raise ValueError("TYPE block declares no data type")

    struct = _STRUCT_START_RE.fullmatch(body[0])
    if struct:
        if len(body) < 2 or not _STRUCT_END_RE.fullmatch(body[-1]):
            raise ValueError("structure is missing END_STRUCT;")

        fields: list[StructureField] = []
        for line in body[1:-1]:
            field = _FIELD_RE.fullmatch(line)
            if field is None:
                raise ValueError(f'invalid structure field: "{line}"')
            fields.append(
                {
                    "name": field.group("name"),
                    "type": _declared_type(field.group("type")),
                    "initial_value": (
                        field.group("initial").strip() if field.group("initial") else None
                    ),
                    "documentation": (
                        field.group("documentation").strip()
                        if field.group("documentation")
                        else None
                    ),
                }
            )
        result: DataTypeInfo = {
            "name": struct.group("name"),
            "kind": "structure",
            "fields": fields,
        }
    else:
        if len(body) != 1:
            raise ValueError("a .dt file must declare exactly one data type")

        enum = _ENUM_RE.fullmatch(body[0])
        if enum:
            raw_values = enum.group("values").strip()
            values = [] if not raw_values else [value.strip() for value in raw_values.split(",")]
            invalid = next(
                (value for value in values if re.fullmatch(_IDENTIFIER, value) is None), None
            )
            if invalid is not None:
                raise ValueError(f'invalid enumeration value: "{invalid}"')
            result = {
                "name": enum.group("name"),
                "kind": "enumerated",
                "values": values,
                "initial_value": enum.group("initial").strip() if enum.group("initial") else None,
            }
        else:
            array = _ARRAY_RE.fullmatch(body[0])
            if array is None:
                raise ValueError(f'invalid declaration: "{body[0]}"')
            result = {
                "name": array.group("name"),
                "kind": "array",
                "base_type": array.group("base"),
                "dimensions": _dimensions(array.group("dimensions")),
                "initial_value": array.group("initial").strip() if array.group("initial") else None,
            }

    if result["name"].casefold() != expected_name.casefold():
        raise ValueError(
            f'declared type name "{result["name"]}" does not match filename identity '
            f'"{expected_name}"'
        )
    result["name"] = expected_name
    return result


def _legacy_type(value: object) -> str:
    if isinstance(value, str):
        return _declared_type(value)
    if not isinstance(value, dict):
        raise ValueError("legacy declared type must be an object")

    definition = value.get("definition")
    if definition == "array":
        data = value.get("data")
        if not isinstance(data, dict):
            raise ValueError("legacy array type is missing data")
        base_type = data.get("baseType")
        if not isinstance(base_type, dict):
            raise ValueError("legacy array type is missing baseType")
        base_value = base_type.get("value")
        if not isinstance(base_value, str) or not base_value.strip():
            raise ValueError("legacy array type is missing baseType.value")
        raw_dimensions = data.get("dimensions")
        if not isinstance(raw_dimensions, list):
            raise ValueError("legacy array type dimensions must be an array")
        dimensions = [_legacy_dimension(item, index) for index, item in enumerate(raw_dimensions)]
        if not dimensions:
            raise ValueError("legacy array type must contain at least one dimension")
        return f'ARRAY [{", ".join(dimensions)}] OF {base_value.strip()}'

    type_value = value.get("value")
    if not isinstance(type_value, str) or not type_value.strip():
        raise ValueError("legacy declared type is missing value")
    return _declared_type(type_value)


def _legacy_dimension(value: object, index: int) -> str:
    if not isinstance(value, dict):
        raise ValueError(f"legacy array dimension at index {index} is not an object")
    dimension = value.get("dimension")
    if not isinstance(dimension, str) or not dimension.strip():
        raise ValueError(f"legacy array dimension at index {index} is invalid")
    return dimension.strip()


def _legacy_structure_initial(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("legacy structure field initialValue must be an object")
    simple_value = value.get("simpleValue")
    if not isinstance(simple_value, dict):
        raise ValueError("legacy structure field initialValue.simpleValue must be an object")
    return _optional_text(simple_value.get("value"), "initialValue.simpleValue.value")


def _legacy_data_type(value: object, index: int) -> DataTypeInfo:
    if not isinstance(value, dict):
        raise ValueError(f"legacy data type at index {index} is not an object")

    name = value.get("name")
    if not isinstance(name, str) or re.fullmatch(_IDENTIFIER, name.strip()) is None:
        raise ValueError(f"legacy data type at index {index} has an invalid name")
    name = name.strip()

    derivation = value.get("derivation")
    if derivation == "enumerated":
        raw_values = value.get("values")
        if not isinstance(raw_values, list):
            raise ValueError(f'legacy enumerated data type "{name}" values must be an array')
        values: list[str] = []
        for value_index, item in enumerate(raw_values):
            if not isinstance(item, dict):
                raise ValueError(
                    f'legacy enumerated data type "{name}" value at index {value_index} '
                    "is not an object"
                )
            description = item.get("description")
            if not isinstance(description, str) or re.fullmatch(_IDENTIFIER, description.strip()) is None:
                raise ValueError(
                    f'legacy enumerated data type "{name}" value at index {value_index} is invalid'
                )
            values.append(description.strip())
        return {
            "name": name,
            "kind": "enumerated",
            "values": values,
            "initial_value": _optional_text(value.get("initialValue"), "initialValue"),
        }

    if derivation == "structure":
        raw_fields = value.get("variable")
        if not isinstance(raw_fields, list):
            raise ValueError(f'legacy structure data type "{name}" variable must be an array')
        fields: list[StructureField] = []
        for field_index, item in enumerate(raw_fields):
            if not isinstance(item, dict):
                raise ValueError(
                    f'legacy structure data type "{name}" field at index {field_index} is not an object'
                )
            field_name = item.get("name")
            if not isinstance(field_name, str) or re.fullmatch(_IDENTIFIER, field_name.strip()) is None:
                raise ValueError(
                    f'legacy structure data type "{name}" field at index {field_index} has an invalid name'
                )
            fields.append(
                {
                    "name": field_name.strip(),
                    "type": _legacy_type(item.get("type")),
                    "initial_value": _legacy_structure_initial(item.get("initialValue")),
                    "documentation": _optional_text(item.get("documentation"), "documentation"),
                }
            )
        return {"name": name, "kind": "structure", "fields": fields}

    if derivation == "array":
        raw_dimensions = value.get("dimensions")
        if not isinstance(raw_dimensions, list):
            raise ValueError(f'legacy array data type "{name}" dimensions must be an array')
        dimensions = [
            _legacy_dimension(item, dimension_index)
            for dimension_index, item in enumerate(raw_dimensions)
        ]
        if not dimensions:
            raise ValueError(f'legacy array data type "{name}" must contain at least one dimension')
        return {
            "name": name,
            "kind": "array",
            "base_type": _legacy_type(value.get("baseType")),
            "dimensions": dimensions,
            "initial_value": _optional_text(value.get("initialValue"), "initialValue"),
        }

    raise ValueError(f'legacy data type "{name}" has unsupported derivation')


def _legacy_data_types(project: dict[str, object]) -> list[DataTypeInfo]:
    data = project.get("data")
    if data is None:
        return []
    if not isinstance(data, dict):
        raise ToolError("project.json data must be an object")

    raw_data_types = data.get("dataTypes", [])
    if not isinstance(raw_data_types, list):
        raise ToolError("project.json data.dataTypes must be an array")

    try:
        return [_legacy_data_type(value, index) for index, value in enumerate(raw_data_types)]
    except ValueError as exc:
        raise ToolError(f"Could not read legacy data types: {exc}") from exc


def list_datatypes(project_path: str) -> list[DataTypeInfo]:
    """List project-defined OpenPLC data types sorted by name."""
    root, _, _, project = load_project_document(project_path)
    data_type_files = list_source_files(root, "datatypes", {".dt"})

    if data_type_files:
        data_types: list[DataTypeInfo] = []
        for path in data_type_files:
            expected_name = path.stem
            try:
                content = path.read_text(encoding="utf-8")
                data_types.append(_parse_dt(content, expected_name))
            except (OSError, UnicodeError, ValueError) as exc:
                raise ToolError(f'Could not read data type "{expected_name}": {exc}') from exc
    else:
        data_types = _legacy_data_types(project)

    return sorted(data_types, key=lambda data_type: data_type["name"].casefold())
