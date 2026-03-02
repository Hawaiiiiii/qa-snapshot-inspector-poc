"""Device profile and capability detection for rack/emulator modes."""

from __future__ import annotations

from dataclasses import dataclass

from qa_snapshot_tool.adb_manager import AdbManager


@dataclass(frozen=True)
class DeviceCapabilities:
    environment_type: str
    profile: str
    supports_uia_dump: bool
    supports_multi_display: bool
    supports_scrcpy: bool
    supports_screencap: bool
    supports_input: bool


def _looks_like_emulator(serial: str) -> bool:
    if (serial or "").startswith("emulator-"):
        return True
    lower = (serial or "").lower()
    return "127.0.0.1:" in lower or "localhost:" in lower


def detect_capabilities(serial: str, emulator_beta_enabled: bool) -> DeviceCapabilities:
    serial = (serial or "").strip()
    model = (AdbManager.getprop(serial, "ro.product.model") or "").lower()
    hardware = (AdbManager.getprop(serial, "ro.hardware") or "").lower()
    manufacturer = (AdbManager.getprop(serial, "ro.product.manufacturer") or "").lower()

    emulator = _looks_like_emulator(serial) or any(
        token in model or token in hardware or token in manufacturer
        for token in ("emulator", "sdk", "goldfish", "ranchu")
    )

    if emulator:
        if "automotive" in model or "car" in model or "aaos" in model:
            profile = "aaos_emulator"
        else:
            profile = "android_studio_emulator"
        environment_type = "emulator"
    else:
        profile = "rack_aaos"
        environment_type = "rack"

    display_ids = AdbManager.get_display_ids(serial)
    supports_uia_dump = AdbManager.has_uiautomator_service(serial)
    supports_multi_display = len(display_ids) > 1

    # Emulator support is explicit beta-only in 2.0 policy.
    if environment_type == "emulator" and not emulator_beta_enabled:
        supports_scrcpy = False
        supports_screencap = False
        supports_input = False
        supports_uia_dump = False
    else:
        supports_scrcpy = True
        supports_screencap = True
        supports_input = True

    return DeviceCapabilities(
        environment_type=environment_type,
        profile=profile,
        supports_uia_dump=supports_uia_dump,
        supports_multi_display=supports_multi_display,
        supports_scrcpy=supports_scrcpy,
        supports_screencap=supports_screencap,
        supports_input=supports_input,
    )
