# Troubleshooting guide

Stuck? Here are solutions to the most common problems.

## 1. "No device found" / device list is empty

This is the most common issue.
*   **Check the cable**: Ensure you are using a high-quality data cable, not just a charging cable.
*   **Trust the computer**: Unlock your phone. Did a popup ask "Allow USB debugging?" You must click **Allow**.
*   **Developer options**: Verify that "USB debugging" is actually toggled ON in your phone's Developer settings.
*   **Nuclear option**: If nothing works, run this in your terminal to reset the connection:
    ```bash
    adb kill-server
    adb start-server
    ```

> [!TIP]
> Try a different USB cable if the device still does not show up.

## 2. "Parse error" or app crashes

If the app crashes immediately after taking a snapshot:
*   **What happened?** The XML blueprint from the phone was likely corrupted or contained illegal characters.
*   **Solution**: Close the error, navigate to a slightly different screen on the phone, and try again.
*   **Reporting**: If it happens consistently, share the `dump.uix` file with the dev team (via GitHub Issues).

> [!CAUTION]
> Corrupted dumps are common on heavy UI screens. Re-capture before reporting.

## 3. Black screenshots (the "security" problem)

*   **Symptom**: You capture a snapshot, but the image is completely black.
*   **Cause**: The app you are testing has `FLAG_SECURE` enabled. This is common in banking apps, Netflix, or login screens to prevent spyware.
*   **Solution**: You must use a **debug/QA build** of your application where this security flag is disabled. We cannot bypass Android's OS-level security.

### Secure surface limitations (AAOS / BMW)

Some surfaces are protected by `FLAG_SECURE` or secure buffers (maps, PIN entry, protected media, system overlays). When this happens:

*   The screenshot may be black.
*   The UI hierarchy may miss secure layers.
*   Header/footer overlays can be missing from the tree.

QUANTUM will now log detected secure layers (best effort) in the System Log.

**Mitigation**: Use a debug ECU build with `ro.secure=0` or a QA build that disables `FLAG_SECURE` for testing.

> [!WARNING]
> Do not attempt to bypass OS-level security protections.

## 4. Elements are misaligned

*   **Symptom**: The red box is slightly to the left or right of the actual button.
*   **Cause**: This often happens on devices with "Notch" cameras or hidden navigation bars.
*   **Fix**: Try rotating the device to landscape and back to portrait, then capture again.

## 5. Low FPS with scrcpy

*   **Symptom**: The live view feels smooth but never reaches >30 FPS.
*   **Cause**: Windows composition and off‑screen capture can cap throughput on some GPUs.
*   **Fixes**:
    *   Enable **Prefer raw H.264 stream (PyAV)** in the Live Mirror panel.
    *   Ensure `av` is installed (`pip install -r requirements.txt`).
    *   Reduce Max Size to 1080p or 720p for a stable frame rate.

## 6. Remote ADB device farm not showing devices

*   **Symptom**: No devices show up after setting a remote ADB server.
*   **Fixes**:
    *   Verify the host and port (default ADB port is 5037).
    *   Confirm the remote server allows ADB connections from your machine.
    *   Clear the ADB server field to return to local devices.
