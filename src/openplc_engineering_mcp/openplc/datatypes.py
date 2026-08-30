"""OpenPLC project-defined data type inspection."""

import re
from typing import Literal, TypedDict

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import list_source_files, load_project_document


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


def list_datatypes(project_path: str) -> list[DataTypeInfo]:
    """List project-defined data types from the current OpenPLC .dt format."""
    root, _, _, project = load_project_document(project_path)
    data_type_files = list_source_files(root, "datatypes", {".dt"})

    if not data_type_files:
        data = project.get("data")
        if isinstance(data, dict) and data.get("dataTypes"):
            raise ToolError(
                "Unsupported OpenPLC project format: data types must be stored in datatypes/*.dt"
            )
        return []

    data_types: list[DataTypeInfo] = []
    for path in data_type_files:
        expected_name = path.stem
        try:
            content = path.read_text(encoding="utf-8")
            data_types.append(_parse_dt(content, expected_name))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ToolError(f'Could not read data type "{expected_name}": {exc}') from exc

    return sorted(data_types, key=lambda data_type: data_type["name"].casefold())
