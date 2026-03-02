from qa_snapshot_tool.device_profiles import detect_capabilities


def test_emulator_caps_blocked_when_beta_disabled(monkeypatch):
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.getprop", lambda _s, _p: "sdk")
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.get_display_ids", lambda _s: ["0", "1"])
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.has_uiautomator_service", lambda _s: True)

    caps = detect_capabilities("emulator-5554", emulator_beta_enabled=False)

    assert caps.environment_type == "emulator"
    assert caps.profile == "android_studio_emulator"
    assert caps.supports_multi_display is True
    assert caps.supports_scrcpy is False
    assert caps.supports_screencap is False
    assert caps.supports_input is False
    assert caps.supports_uia_dump is False


def test_emulator_caps_enabled_when_beta_enabled(monkeypatch):
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.getprop", lambda _s, _p: "aaos")
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.get_display_ids", lambda _s: ["0"])
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.has_uiautomator_service", lambda _s: True)

    caps = detect_capabilities("emulator-5554", emulator_beta_enabled=True)

    assert caps.environment_type == "emulator"
    assert caps.supports_uia_dump is True
    assert caps.supports_scrcpy is True
    assert caps.supports_screencap is True
    assert caps.supports_input is True


def test_rack_profile_detected(monkeypatch):
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.getprop", lambda _s, _p: "BMW-RACK")
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.get_display_ids", lambda _s: ["0"])
    monkeypatch.setattr("qa_snapshot_tool.device_profiles.AdbManager.has_uiautomator_service", lambda _s: True)

    caps = detect_capabilities("RACK123", emulator_beta_enabled=False)

    assert caps.environment_type == "rack"
    assert caps.profile == "rack_aaos"
    assert caps.supports_scrcpy is True
    assert caps.supports_screencap is True
    assert caps.supports_input is True
    assert caps.supports_uia_dump is True
