"""OpenPLC physical I/O configuration inspection."""

import json
from pathlib import Path
from typing import Literal, TypedDict, cast

from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.project import load_project

PinType = Literal["digitalInput", "digitalOutput", "analogInput", "analogOutput"]
_PIN_TYPES = {"digitalInput", "digitalOutput", "analogInput", "analogOutput"}
_DEFAULT_DEVICE_BOARD = "OpenPLC Simulator"


class IOPoint(TypedDict):
    pin: str
    pin_type: PinType
    address: str
    alias: str | None


class IOConfiguration(TypedDict):
    device_board: str
    io_points: list[IOPoint]


def _read_device_json(path: Path, label: str) -> object:
    """Read one current-format OpenPLC device JSON file."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ToolError(f"Could not read {label}: {exc}") from exc

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ToolError(f"{label} is not valid JSON: {exc.msg}") from exc


def _load_device_board(root: Path) -> str:
    path = root / "devices" / "configuration.json"
    if not path.is_file():
        return _DEFAULT_DEVICE_BOARD

    configuration = _read_device_json(path, "devices/configuration.json")
    if not isinstance(configuration, dict):
        raise ToolError("devices/configuration.json must contain a JSON object")

    device_board = configuration.get("deviceBoard", _DEFAULT_DEVICE_BOARD)
    if not isinstance(device_board, str):
        raise ToolError("devices/configuration.json deviceBoard must be a string")
    return device_board


def _parse_pin(pin: object, board: str, index: int) -> IOPoint:
    if not isinstance(pin, dict):
        raise ToolError(f'devices/pin-mapping.json board "{board}" pin {index} must be an object')

    if "name" in pin and "alias" not in pin:
        raise ToolError(
            "Unsupported OpenPLC project format: devices/pin-mapping.json uses legacy pin name"
        )

    pin_number = pin.get("pin")
    pin_type = pin.get("pinType")
    address = pin.get("address")
    alias = pin.get("alias")

    prefix = f'devices/pin-mapping.json board "{board}" pin {index}'
    if not isinstance(pin_number, str) or not pin_number:
        raise ToolError(f"{prefix}.pin must be a non-empty string")
    if pin_type not in _PIN_TYPES:
        raise ToolError(f"{prefix}.pinType must be a supported OpenPLC pin type")
    if not isinstance(address, str):
        raise ToolError(f"{prefix}.address must be a string")
    if "alias" in pin and not isinstance(alias, str):
        raise ToolError(f"{prefix}.alias must be a string when present")

    return {
        "pin": pin_number,
        "pin_type": cast(PinType, pin_type),
        "address": address,
        "alias": alias if isinstance(alias, str) else None,
    }


def _load_pin_mappings(root: Path) -> dict[str, list[IOPoint]]:
    path = root / "devices" / "pin-mapping.json"
    if not path.is_file():
        return {}

    mapping = _read_device_json(path, "devices/pin-mapping.json")
    if isinstance(mapping, list):
        raise ToolError(
            "Unsupported OpenPLC project format: devices/pin-mapping.json must use per-board mappings"
        )
    if not isinstance(mapping, dict):
        raise ToolError("devices/pin-mapping.json must contain a per-board JSON object")

    parsed: dict[str, list[IOPoint]] = {}
    for board, pins in mapping.items():
        if not isinstance(board, str):
            raise ToolError("devices/pin-mapping.json board names must be strings")
        if not isinstance(pins, list):
            raise ToolError(f'devices/pin-mapping.json board "{board}" must contain an array')
        parsed[board] = [_parse_pin(pin, board, index) for index, pin in enumerate(pins)]
    return parsed


def get_io_configuration(project_path: str) -> IOConfiguration:
    """Return the selected board and its current local physical I/O mapping."""
    root, _, project_type = load_project(project_path)
    if project_type != "plc-project":
        raise ToolError("I/O configuration is only available for OpenPLC plc-project projects")

    device_board = _load_device_board(root)
    mappings = _load_pin_mappings(root)
    return {"device_board": device_board, "io_points": mappings.get(device_board, [])}
