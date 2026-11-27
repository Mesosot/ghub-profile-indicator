# Changelog

## 1.0.1 — 2026-11-27

### Added

- Rename the app to **Logitech G HUB Profile Indicator**, including its window, tray identity and Windows file properties.
- Add an opt-in **Start with Windows** checkbox that can be enabled or disabled without administrator rights.
- Introduce a compact **G** circle with a tiny live profile caption underneath; long names expand to their full label.
- Automatically expand for **5 seconds** when the active profile changes, restarting the preview for each new change.
- Expand on hover or click for **10 seconds**, with manual expand/collapse controls.

### Improved

- Add a liquid-glass-inspired dark finish with antialiased translucent edges, fine rims, highlights and soft shadows.
- Use smooth, damped morph animations and cache artwork to avoid unnecessary idle redraws.
- Keep tray-hidden overlays hidden and defer profile-change previews while dragging or using the menu.
- Preserve the existing executable name and settings location for upgrades and startup compatibility.

### Fixed

- Fix the overlay jumping back to an old position after dragging, expanding or collapsing.
- Preserve the last dragged compact anchor even when dragging during an animation.
- Prevent screen-edge clamping from changing the saved position.
- Support placement on monitors to the left of or above the primary screen.
- Show an unavailable caption when the live connection is lost instead of retaining a stale name.

### Validation

- Reader, startup, UI, glass rendering and position-regression tests are included.
- Native Windows checks verified five-second change previews, saved drag placement and stable GDI resource counts.

## 1.0.0

- Read the live effective software profile directly from the running G HUB agent.
- Movable always-on-top overlay with saved position.
- Optional native Windows tray icon and profile-change notifications.
- Visible unavailable state and automatic reconnection.
- Read-only application-name lookup with SQLite WAL support.
- Portable Windows x64 executable and runnable Python source.
