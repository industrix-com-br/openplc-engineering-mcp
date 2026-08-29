import json
import re
from typing import Literal, TypedDict, cast

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.pous import read_pou

VariableClass = Literal["input", "output", "inOut", "external", "local", "temp", "global"]
VariableInfo = TypedDict(
    "VariableInfo",
    {
        "name": str,
        "class": VariableClass,
        "type": str,
        "location": str | None,
        "initial_value": str | None,
        "documentation": str | None,
    },
)

_VARIABLE_CLASSES: dict[str, VariableClass] = {
    "VAR_INPUT": "input",
    "VAR_OUTPUT": "output",
    "VAR_IN_OUT": "inOut",
    "VAR_EXTERNAL": "external",
    "VAR_TEMP": "temp",
    "VAR_GLOBAL": "global",
    "VAR": "local",
}
_DISALLOWED_LOCATION_CLASSES: frozenset[VariableClass] = frozenset(
    {"input", "output", "inOut", "external", "temp"}
)
_BLOCK_START_RE = re.compile(
    r"^\s*(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_EXTERNAL|VAR_TEMP|VAR_GLOBAL|VAR)\b",
    re.IGNORECASE,
)
_END_VAR_RE = re.compile(r"^\s*END_VAR\b", re.IGNORECASE)
_DECLARATION_RE = re.compile(
    r"^\s*(?P<name>\w+)\s*:\s*(?P<type>[\w\s\[\],.]+?)"
    r"(?:\s+AT\s+(?P<location>[\w\d._%]+))?\s*"
    r"(?::=\s*(?P<initial_value>[^;]+?))?\s*;\s*"
    r"(?:\(\*\s*(?P<documentation>.*?)\s*\*\))?\s*$",
    re.IGNORECASE,
)
_ALTERNATE_DECLARATION_RE = re.compile(
    r"^\s*(?P<name>\w+)\s+AT\s+(?P<location>[\w\d._%]+)\s*:\s*"
    r"(?P<type>[\w\s\[\],.]+?)\s*(?::=\s*(?P<initial_value>[^;]+?))?\s*;\s*"
    r"(?:\(\*\s*(?P<documentation>.*?)\s*\*\))?\s*$",
    re.IGNORECASE,
)


def _optional_text(value: object, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f'JSON variable field "{field}" must be a string or null')
    stripped = value.strip()
    return stripped or None


def _json_type(value: object) -> str:
    if isinstance(value, str):
        declared_type = value.strip()
    elif isinstance(value, dict):
        type_value = value.get("value")
        declared_type = type_value.strip() if isinstance(type_value, str) else ""
    else:
        declared_type = ""

    if not declared_type:
        raise ValueError("JSON variable is missing a declared type")
    return declared_type


def _json_variable(value: object, index: int) -> VariableInfo:
    if not isinstance(value, dict):
        raise ValueError(f"JSON variable at index {index} is not an object")

    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"JSON variable at index {index} is missing a name")

    variable_class = value.get("class")
    if variable_class not in _VARIABLE_CLASSES.values():
        raise ValueError(f'JSON variable "{name}" has an unsupported or missing class')

    return {
        "name": name.strip(),
        "class": cast(VariableClass, variable_class),
        "type": _json_type(value.get("type")),
        "location": _optional_text(value.get("location"), "location"),
        "initial_value": _optional_text(value.get("initialValue"), "initialValue"),
        "documentation": _optional_text(value.get("documentation"), "documentation"),
    }


def _json_variables(content: str) -> list[VariableInfo]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON representation: {exc.msg}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("unsupported JSON POU representation")

    raw_variables: object
    data = parsed.get("data")
    if isinstance(parsed.get("type"), str) and isinstance(data, dict):
        raw_variables = data.get("variables", [])
    else:
        interface = parsed.get("interface")
        if isinstance(interface, dict):
            raw_variables = interface.get("variables", [])
        elif isinstance(parsed.get("variables"), list):
            raw_variables = parsed["variables"]
        elif "pouType" in parsed or "body" in parsed:
            raw_variables = []
        else:
            raise ValueError("unsupported JSON POU representation")

    if not isinstance(raw_variables, list):
        raise ValueError("JSON POU variables must be a list")

    return [_json_variable(variable, index) for index, variable in enumerate(raw_variables)]


def _source_variables(content: str) -> list[VariableInfo]:
    variables: list[VariableInfo] = []
    current_class: VariableClass | None = None
    block_start_line: int | None = None

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        block_start = _BLOCK_START_RE.match(line)
        if block_start:
            if current_class is not None:
                raise ValueError(f"variable block started on line {block_start_line} is missing END_VAR")
            current_class = _VARIABLE_CLASSES[block_start.group(1).upper()]
            block_start_line = line_number
            continue

        if _END_VAR_RE.match(line):
            current_class = None
            block_start_line = None
            continue

        if current_class is None:
            continue

        declaration = _DECLARATION_RE.match(line) or _ALTERNATE_DECLARATION_RE.match(line)
        if declaration is None:
            raise ValueError(f'unrecognized declaration on line {line_number}: "{line}"')

        location = declaration.group("location")
        initial_value = declaration.group("initial_value")
        if location and current_class in _DISALLOWED_LOCATION_CLASSES:
            raise ValueError(
                f'location is not allowed for variable class "{current_class}" on line {line_number}'
            )
        if initial_value and current_class == "external":
            raise ValueError(
                f'initial value is not allowed for variable class "external" on line {line_number}'
            )

        documentation = declaration.group("documentation")
        variables.append(
            {
                "name": declaration.group("name").strip(),
                "class": current_class,
                "type": declaration.group("type").strip(),
                "location": location.strip() if location else None,
                "initial_value": initial_value.strip() if initial_value else None,
                "documentation": documentation.strip() if documentation else None,
            }
        )

    if current_class is not None:
        raise ValueError(f"variable block started on line {block_start_line} is missing END_VAR")

    return variables


def list_variables(project_path: str, pou_name: str) -> list[VariableInfo]:
    """List variables declared by a POU in source declaration order."""
    pou = read_pou(project_path, pou_name)

    try:
        if pou["language"] is None:
            return _json_variables(pou["content"])
        return _source_variables(pou["content"])
    except ValueError as exc:
        raise ToolError(f'Could not read variables for POU "{pou["name"]}": {exc}') from exc
