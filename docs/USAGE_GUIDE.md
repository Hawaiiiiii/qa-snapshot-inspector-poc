# User guide

From zero to hero: how to use QUANTUM Inspector to debug your apps.

## Prerequisites (getting ready)

Before you launch the app, make sure you have:
1.  **USB debugging enabled**: On your phone, go to **Settings -> Developer options** and enable **USB debugging**.
2.  **Connection**: Plug your phone into your PC via USB. (Accept "Trust this computer" on your phone screen if prompted).

## Step 1: Launching the app

Open your terminal in the project folder and run:
```bash
python src/qa_snapshot_tool/main.py
```
You will see the dark-themed interface appear.

> [!TIP]
> You can run the app without a device and inspect offline snapshots immediately.

## Step 2: Selecting your device

In the top left corner of the app:
*   **Device list**: You should see your device ID here.
*   **If it works**: Great!
*   **If it is empty**: Click the **Refresh** button. If it is still empty, check your USB cable.

> [!NOTE]
> For Wi‑Fi devices, use the IP:port field and Connect IP.

### Optional: device farm / remote ADB server

If your devices are hosted in a remote lab or emulator farm, you can route all ADB commands through a remote server:

1. Enter host:port in **ADB server host:port** (e.g., `10.10.20.12:5037`).
2. Click **Set ADB Server**.
3. Refresh the device list.

To return to local ADB, clear the field and click **Set ADB Server**.

## Step 3: Taking a snapshot (the magic moment)

1.  Pick up your phone and navigate to the screen you want to capture (e.g., a bug where the login button is broken).
2.  In the app, click the big **"Capture snapshot"** button.
3.  Wait a few seconds... (The tool is downloading the image and data).
4.  **Done!** Your phone screen will appear in the main window.

> [!WARNING]
> Some apps use Android secure flags and may produce black screenshots.

## Step 4: Investigating elements

This is where you find the hidden details.
*   **Hover**: Move your mouse over the screenshot. Red boxes will light up to show you what the phone "thinks" are clickable items.
*   **Click**: Detailed properties will appear in the **Right panel**.
*   **Copy code**: Need to write an automated test? Look at the **Locator suggestions** box. We act as a "consultant" and give you the best XPath or ID to use.

## Pro tips

*   **Offline mode**: You don't need a phone connected to view old snapshots! Just use **File -> Load snapshot** and pick any `snap_...` folder from before.
*   **Logcat**: Every timestamped folder also contains a `logcat.txt`. Give this to your developers; they will love you for it.
