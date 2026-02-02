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

> [!WARNING]
> Do not attempt to bypass OS-level security protections.

## 4. Elements are misaligned

*   **Symptom**: The red box is slightly to the left or right of the actual button.
*   **Cause**: This often happens on devices with "Notch" cameras or hidden navigation bars.
*   **Fix**: Try rotating the device to landscape and back to portrait, then capture again.
