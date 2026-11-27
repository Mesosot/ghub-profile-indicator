# Logitech G HUB Profile Indicator

A small, movable, always-on-top Windows overlay that reads the **effective profile reported by the running G HUB agent**. It does not predict the profile from the foreground program, and it never switches profiles.

The interface uses a liquid-glass-inspired dark finish: antialiased translucent edges, reflected highlights and soft shadows, with smooth damped expansion. This is a custom visual treatment with real alpha transparency; it does not capture the desktop or apply Apple's system material or live background blur.

## Download

**[Download Logitech G HUB Profile Indicator 1.0.1 for Windows x64](https://github.com/Mesosot/ghub-profile-indicator/releases/download/v1.0.1/Logitech-G-HUB-Profile-Indicator-Windows-x64.zip)** · [Changelog](CHANGELOG.md) · [Release notes](https://github.com/Mesosot/ghub-profile-indicator/releases/tag/v1.0.1)

Extract the ZIP and double-click `GHubIndicator.exe`. The portable download includes the app and license notices. No Python installation is required. Source code is available in this repository.

## Run the Windows app

1. Keep Logitech G HUB running in the background. Its main window can be minimized or closed to the tray.
2. Double-click `GHubIndicator.exe` in the portable download. No Python, administrator rights, or installation is required. This build is unsigned.
3. The indicator starts as a small rounded **G** circle with the live profile in a tiny caption underneath. Long captions use an ellipsis; hover or click to see the full name. A profile change opens an animated preview for **5 seconds**, then shrinks back. Each new change restarts the five-second preview. Hovering/clicking manually uses **10 seconds**. Timers pause while its menu is open, and a tray-hidden overlay stays hidden. Move the pointer away and back to reopen after automatic collapse, or click the circle.
4. Drag the circle or expanded overlay to a convenient spot. Its compact position is saved independently of the animation, so opening and closing returns it to the last dragged location. Screens to the left of or above the primary monitor are supported.
5. Right-click anywhere on it, or click **⋯** when expanded, for manual expand/collapse, notifications, the optional tray icon, startup, connection details and Quit.
6. Double-click the tray icon to hide/show the overlay. Notifications are off initially. Windows notification settings can suppress tray notifications. With the tray disabled, changes use a brief floating message instead.

The overlay polls once per second. Failed connections retry automatically, with a delay of up to five seconds. It shows **Profile unavailable** when live reads fail, rather than leaving an old profile displayed as current.

To start with Windows, open **⋯ → Start with Windows** and check the option. Uncheck it to stop automatic startup. It starts when your Windows account signs in, requires no administrator rights, and is off until you enable it. Keep the EXE in a permanent folder before enabling startup. If you move it later, turn this option off and on again from the new location. A manually created Startup-folder shortcut is separate; remove any old shortcut to avoid a second launch. Windows Task Manager can also disable startup independently of this checkbox.

## What it reads

The live source is `ws://127.0.0.1:9010`, the running G HUB agent's local WebSocket interface. Requests use the `json` subprotocol and `file://` Origin. The application sends only allowlisted **GET** requests:

| Request | Purpose |
|---|---|
| `/profile/effective` | Read the reported effective software profile, its ID, name and application ID. |
| `/devices/list` | Check active-device and onboard-mode state, so the UI can warn about software-only readings. |
| `/profile/active` | Read-only diagnostic capability, not used for deciding what the overlay displays. |

`%LOCALAPPDATA%\LGHUB\settings.db` supplies application **display names only**. It is opened using SQLite `mode=ro` and `query_only`, including committed WAL changes. If the catalog cannot be read, the live profile still displays with an application-ID label. The app does not use `activeForApplication` to select the live profile: that flag is set on multiple profiles in the observed installation.

There are no SET, POST, profile activation, device writes, hooks, injection, Lua changes, or foreground-process matching. No G HUB database changes, process restarts, or configuration changes are performed. SQLite may use its normal shared-memory reader coordination for an existing WAL database; this is not a database-content modification. Only the indicator's own preferences are saved under `%LOCALAPPDATA%\GHubIndicator\config.json`. There is no Internet access or telemetry in the indicator. Connections are fixed to loopback, and proxy use is explicitly bypassed.

## Limitations — please read

- **Private, unofficial interface.** This is a tested G HUB internal endpoint, not a documented/supported public Logitech API. Logitech updates can change its port, protocol or response structure. The indicator fails visibly if that happens. It never silently changes to estimated detection.
- **Software state, not physical-device verification.** It reports G HUB's effective software profile. A device using onboard memory can have different settings. When the agent reports onboard mode, the overlay warns about that. Per-device configuration profiles, G-Shift, persistent individual feature assignments, hardware slots and actual button effects are not independently decoded.
- A persistent profile is handled by reading the reported effective state, not guessing based on the active game. Persistent-profile behavior needs a live check on the specific G HUB version; it was not changed on the development test installation.
- One-second polling can miss profiles that activate and deactivate between polls. The database name catalog refreshes every five seconds, so app renames can lag briefly.
- G HUB must be running and responsive. The app can work while the G HUB window is hidden, but cannot read a stopped agent. If the device-state query fails, this build conservatively marks the reading unavailable as well.
- Windows can place exclusive-fullscreen games above ordinary topmost desktop windows. Use borderless/windowed mode when needed. This is a desktop overlay, with no game injection.
- Desktop and Default localization tokens are translated to English; other unfamiliar localization tokens are shown as returned.
- Normal overlay clicks are marked nonactivating to avoid changing the foreground app. Opening a menu/dialog can still affect focus and G HUB's ordinary automatic switching.
- The loopback protocol is unauthenticated. This app is not designed to defend against another malicious process already running locally and impersonating G HUB.

## Run from source

Requires Windows 10/11 x64 and Python 3.12 with Tkinter. From this folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Tkinter and SQLite are included in the standard Windows Python installer. Pillow renders the antialiased glass artwork; Windows presents it using a per-pixel-alpha layered window. The tray uses the Windows notification-area API directly.

Build the portable EXE with `build.ps1` or run:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name GHubIndicator --version-file version_info.txt app.py
```

The result is `dist\GHubIndicator.exe`. A one-file bundle extracts its runtime to a temporary folder on launch. No additional Windows service is installed.

## Troubleshooting / local diagnostics

Use **⋯ → Connection details / limitations** to inspect the last connection error. Check that G HUB itself is running. An incompatible update may require adapting this app; do not delete or edit your G HUB database.

For a minimal local diagnostic report:

```powershell
.\GHubIndicator.exe --diagnose live-report.json
```

The report contains profile/app names and IDs, active-device count and onboard warnings, rather than macros, assignments or device serials. It remains on your PC. An error report exits with code 1. Source equivalent: `python app.py --diagnose live-report.json`.

Optional overrides: `--port 9010`, `--db "C:\path\to\settings.db"`. The host always remains `127.0.0.1`.

## Verification and research

See `VERIFICATION.md` for actual checks and remaining manual checks, and `RESEARCH.md` for primary documentation and GitHub references. No third-party project source was copied into the app.

This independent utility is not affiliated with or endorsed by Logitech.
