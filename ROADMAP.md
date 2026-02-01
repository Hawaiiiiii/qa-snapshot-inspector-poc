# Product roadmap

This document outlines the future of QUANTUM Inspector.

## The vision (v2.0 and beyond)

We want to move from a "Passive Inspector" to an "Active Diagnosis Tool".

### Major feature: "Self-healing locators" (AI)
*   **Problem**: You change the UI text from "Submit" to "Register", and your test breaks.
*   **Solution**: The tool will store history. If "Submit" is gone, it will look for a button in the same place with the ID `btn_register` and suggest the fix.

### Major feature: "Cloud sync"
*   **Concept**: Push a snapshot directly to a shared S3 bucket / Google Drive.
*   **Use Case**: QA takes a snapshot of a bug in London  Dev opens it in New York 5 minutes later without needing the physical device.

### Major feature: "Live mirroring" (low latency)
*   Instead of static snapshots, we want a real-time stream (30fps) where you can interact with the device using your mouse/keyboard.

---

## Short term goals (v1.x polish)

*   [ ] **Keyboard shortcuts**: `Ctrl+S` to save, `Ctrl+R` to refresh.
*   [ ] **Search bar**: Type "login" and filter the view hierarchy tree.
*   [ ] **Export to Jira**: One-click button to copy "Screenshot + Logs + ID" to clipboard formatted for Jira.
*   [ ] **Settings menu**: Allow changing saved screenshot quality (PNG/JPG) to save space.

## Long term / research

*   **iOS support**: This requires `libimobiledevice` integration. It is hard, but necessary for full coverage.
*   **Accessibility scanner**: Automatically flag buttons that are too small or miss "content-description" tags for blind users.
