# Verification

Tested on the current Windows 11 x64 PC, Python 3.12.10, G HUB agent **2026.7.1011216**.

## Passed

- Live direct-agent read matched G HUB's visible **Desktop: Default** header.
- Continuous direct-agent reads captured **Desktop: Default → client: Tibia → Desktop: Default** across application focus changes. The two profiles had different live effective-profile IDs.
- The packaged EXE ran its diagnostic command successfully with exit code 0 and read the running G HUB state.
- The packaged EXE's actual UI was visually inspected: correct live label, no clipping, readable compact dark layout and functioning control menu. For inspection, the hidden QA switch added a normal window frame around the same overlay content.
- Native Windows tray creation, tooltip update and clean deletion were exercised successfully.
- A source UI integration check passed live-state display, native tray initialization, hide/show, disconnect clearing an old profile, reconnect to a different profile, and saved window position. That check injected deterministic agent responses to test failure/recovery without stopping the user's G HUB.
- Eight automated reader tests passed: committed WAL reading, profile identity from the live response, localization/missing catalog, malformed schema, onboard warnings, rejecting non-allowlisted queries before transmission, GET-only request/response handling, and rejected-query errors.
- Build warnings were reviewed: missing modules were optional/platform-specific, including Unix modules and optional WebSocket acceleration/proxy packages. They were not required for the working loopback read.

Run the included reader tests with:

```powershell
python -m unittest discover -s . -v
```

## Not independently verified

- All other G HUB versions and devices, League of Legends/Valorant-specific behavior.
- Persistent-profile selection and a physical device changing to/from onboard mode. The user configuration was not altered for those tests. Onboard warnings were tested with synthetic responses.
- Windows notification delivery under each user's notification settings, multiple monitors with negative coordinates, exclusive fullscreen games, resume from sleep and actual G HUB restart. Failure/recovery was tested with injected responses; actual agent restart was not forced.
- The indicator reports G HUB software state, not physical mouse settings or the correctness of G HUB's own switching behavior.

## Quick acceptance check

1. Launch G HUB and the indicator. Compare the profile labels.
2. Minimize G HUB, focus a configured game for a few seconds, and watch the indicator update. Return to an unmapped app and check the Desktop transition.
3. Optionally enable notifications from **⋯** and repeat. Windows may suppress notification balloons.
4. Drag the overlay, quit it and reopen it to confirm the saved position. Double-click the tray icon to hide/show it.
5. If desired, quit G HUB yourself: the indicator should show unavailable, then recover after G HUB restarts.
6. If you use persistent profiles or onboard mode, check those explicitly against G HUB. An onboard warning means the displayed software profile is not a claim about the physical device's slot.
