# Detection research — 13 November 2026

## Decision

Use G HUB's **live local-agent response**, not foreground-executable inference or a persisted per-app selection flag. This is an unofficial but locally verified method; it must not be described as a supported public Logitech integration.

## Official sources

- [Logitech Developer Alliance / SDK catalog](https://www.logitechg.com/en-us/programs/developer-alliance): lists LED, steering wheel, GamePanel and G-key SDK capabilities. I did not find a documented public API for reading the currently effective global G HUB profile there. This is a search result/conclusion, not proof that no such API could ever exist.
- [Logitech: saving G HUB settings](https://support.logi.com/hc/en-ph/articles/1500005396981-How-can-I-make-sure-my-G-HUB-Settings-are-saved): confirms the Windows LGHUB/settings.db location. It does not document the internal schema or guarantee a live-active-profile field.
- [Logitech: persistent profiles](https://support.logi.com/hc/en-ch/articles/360023371013-G-HUB-Lock-a-profile-for-all-games-and-applications): confirms persistent profiles can apply across applications. This rules out foreground matching as a universally accurate detector.
- [SQLite URI documentation](https://www.sqlite.org/uri.html): documents `mode=ro`. The app uses this for display-name lookup and normal WAL handling.

## GitHub review

- [bmrussell/LGBattery](https://github.com/bmrussell/LGBattery): independently implemented G HUB local-agent WebSocket integration for battery state. Its [endpoint list](https://github.com/bmrussell/LGBattery/blob/main/endpoints.md) identifies `/profile/active`, `/profile/effective`, and `/devices/list`. This was the lead for the read-only probe, not a guarantee of Logitech support. No downloaded repository code was executed or copied.
- [gabfv/logitech-g-hub-settings-extractor](https://github.com/gabfv/logitech-g-hub-settings-extractor): source shows the SQLite JSON-blob layout and selection of the latest row. That utility also writes settings; its editing workflow was not used.
- [Lee-matod/GProfiles](https://github.com/Lee-matod/GProfiles): profile/keymap management using settings.db, not evidence of a supported live profile observer. Not adopted.
- [infinitysky/LogitechGDeviceInfo](https://github.com/infinitysky/LogitechGDeviceInfo): HID++ device information/settings and onboard mode are a different layer from the global G HUB software profile. Not adopted.

## Local evidence

Running agent version: **2026.7.1011216** on this Windows PC.

- `GET /profile/active` returned SUCCESS and a profile ID matching the saved Desktop profile.
- `GET /profile/effective` returned SUCCESS, the same ID, `PROFILE_NAME_DEFAULT`, and the Desktop application ID. The built app reads the ID/name/application ID from this response, not from a process-to-profile prediction.
- The response resolved to **Desktop: Default**, matching the visible G HUB header and the supplied UX screenshots.
- `GET /devices/list` returned an active G502 X with `onboardMode=false`. The app retains only a device count and onboard warnings, not serial numbers or assignment details.
- `GET /profile/persistent` returned INVALID_ARG/no handler. It was rejected as a usable read endpoint and is **not included** in the delivered query allowlist. This demonstrates why listed private endpoint names must be verified instead of assumed to work with GET.
- The database had multiple `activeForApplication=true` profiles simultaneously, confirming that this field alone cannot identify the globally active software profile.
- No useful ordinary `.log` files were found under the installed user's LGHUB tree during the bounded inspection. No stable, documented log feed was established, so log tailing was not implemented.
- The Windows accessibility snapshot of the current G HUB window exposed only generic regions, not the profile text. That ruled out a reliable accessibility-text reader on this installation without further changes.

Subsequent continuous reads captured **Desktop: Default → client: Tibia → Desktop: Default**, with different IDs for Desktop and Tibia, when the existing Tibia client was brought forward and focus later returned. This verifies a real automatic-switch transition through the live endpoint. No foreground-executable inference was involved.

These observations verify a working direct read on this installation, not compatibility with all G HUB versions or physical-device settings. Persistent/onboard behavior should be checked against the acceptance steps in VERIFICATION.md.
