import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from openplc_engineering_mcp.openplc.io import get_io_configuration


def make_project(root: Path, *, project_type: str = "plc-project") -> Path:
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps({"meta": {"name": "Example", "type": project_type}}), encoding="utf-8"
    )
    return root


def write_devices(project: Path, configuration: object, mapping: object) -> None:
    devices = project / "devices"
    devices.mkdir()
    (devices / "configuration.json").write_text(json.dumps(configuration), encoding="utf-8")
    (devices / "pin-mapping.json").write_text(json.dumps(mapping), encoding="utf-8")


def pin(
    pin_number: str = "2",
    pin_type: str = "digitalInput",
    address: str = "%IX0.0",
    alias: str | None = "StartButton",
) -> dict[str, object]:
    result: dict[str, object] = {
        "pin": pin_number,
        "pinType": pin_type,
        "address": address,
    }
    if alias is not None:
        result["alias"] = alias
    return result


def test_active_board_mapping_preserves_current_openplc_pin_contract(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    active_pins = [
        pin("2", "digitalInput", "%IX0.0", "StartButton"),
        pin("13", "digitalOutput", "%QX0.0", "Motor"),
        pin("A0", "analogInput", "%IW0", None),
        pin("3", "analogOutput", "%QW0", "SpeedReference"),
    ]
    write_devices(
        project,
        {"deviceBoard": "Arduino Uno", "communicationPort": "/dev/ttyACM0"},
        {
            "Arduino Uno": active_pins,
            "Arduino Mega": [pin("22", "digitalInput", "%IX1.0", "InactiveBoardInput")],
        },
    )

    result = get_io_configuration(str(project))

    assert result == {
        "device_board": "Arduino Uno",
        "io_points": [
            {
                "pin": "2",
                "pin_type": "digitalInput",
                "address": "%IX0.0",
                "alias": "StartButton",
            },
            {
                "pin": "13",
                "pin_type": "digitalOutput",
                "address": "%QX0.0",
                "alias": "Motor",
            },
            {"pin": "A0", "pin_type": "analogInput", "address": "%IW0", "alias": None},
            {
                "pin": "3",
                "pin_type": "analogOutput",
                "address": "%QW0",
                "alias": "SpeedReference",
            },
        ],
    }


def test_empty_pin_mapping_is_valid(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    write_devices(project, {"deviceBoard": "Arduino Uno"}, {})

    assert get_io_configuration(str(project)) == {
        "device_board": "Arduino Uno",
        "io_points": [],
    }


def test_active_board_without_mapping_is_valid(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    write_devices(
        project,
        {"deviceBoard": "Arduino Uno"},
        {"Arduino Mega": [pin()]},
    )

    assert get_io_configuration(str(project))["io_points"] == []


def test_missing_device_files_use_current_openplc_defaults(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    assert get_io_configuration(str(project)) == {
        "device_board": "OpenPLC Simulator",
        "io_points": [],
    }


def test_configuration_without_device_board_follows_openplc_schema_default(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    devices = project / "devices"
    devices.mkdir()
    (devices / "configuration.json").write_text(
        json.dumps({"communicationPort": "/dev/ttyACM0"}), encoding="utf-8"
    )

    assert get_io_configuration(str(project))["device_board"] == "OpenPLC Simulator"


def test_malformed_device_configuration_json_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    devices = project / "devices"
    devices.mkdir()
    (devices / "configuration.json").write_text("{", encoding="utf-8")

    with pytest.raises(ToolError, match="devices/configuration.json is not valid JSON"):
        get_io_configuration(str(project))


def test_invalid_device_board_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    write_devices(project, {"deviceBoard": 7}, {})

    with pytest.raises(ToolError, match="deviceBoard must be a string"):
        get_io_configuration(str(project))


def test_malformed_pin_mapping_json_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    devices = project / "devices"
    devices.mkdir()
    (devices / "configuration.json").write_text(
        json.dumps({"deviceBoard": "Arduino Uno"}), encoding="utf-8"
    )
    (devices / "pin-mapping.json").write_text("{", encoding="utf-8")

    with pytest.raises(ToolError, match="devices/pin-mapping.json is not valid JSON"):
        get_io_configuration(str(project))


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("2", "pin 0 must be an object"),
        ({"pin": "", "pinType": "digitalInput", "address": "%IX0.0"}, "pin must be"),
        ({"pin": "2", "pinType": "digital", "address": "%IX0.0"}, "pinType must be"),
        ({"pin": "2", "pinType": [], "address": "%IX0.0"}, "pinType must be"),
        ({"pin": "2", "pinType": {}, "address": "%IX0.0"}, "pinType must be"),
        ({"pin": "2", "pinType": "digitalInput", "address": 0}, "address must be"),
        (
            {"pin": "2", "pinType": "digitalInput", "address": "%IX0.0", "alias": 2},
            "alias must be",
        ),
    ],
)
def test_malformed_pin_entries_are_rejected(
    tmp_path: Path, entry: object, message: str
) -> None:
    project = make_project(tmp_path / "project")
    write_devices(project, {"deviceBoard": "Arduino Uno"}, {"Arduino Uno": [entry]})

    with pytest.raises(ToolError, match=message):
        get_io_configuration(str(project))


def test_malformed_inactive_board_mapping_is_not_silently_ignored(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    write_devices(
        project,
        {"deviceBoard": "Arduino Uno"},
        {
            "Arduino Uno": [pin()],
            "Arduino Mega": {"pin": "22"},
        },
    )

    with pytest.raises(ToolError, match='board "Arduino Mega" must contain an array'):
        get_io_configuration(str(project))


def test_legacy_flat_pin_mapping_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    write_devices(project, {"deviceBoard": "Arduino Uno"}, [pin()])

    with pytest.raises(ToolError, match="Unsupported OpenPLC project format"):
        get_io_configuration(str(project))


def test_legacy_pin_name_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    legacy_pin = {
        "pin": "2",
        "pinType": "digitalInput",
        "address": "%IX0.0",
        "name": "StartButton",
    }
    write_devices(project, {"deviceBoard": "Arduino Uno"}, {"Arduino Uno": [legacy_pin]})

    with pytest.raises(ToolError, match="legacy pin name"):
        get_io_configuration(str(project))


def test_library_project_has_no_io_configuration(tmp_path: Path) -> None:
    project = make_project(tmp_path / "library", project_type="plc-library")

    with pytest.raises(ToolError, match="only available for OpenPLC plc-project"):
        get_io_configuration(str(project))


def test_existing_project_loading_errors_are_preserved(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        get_io_configuration(str(tmp_path / "missing"))
