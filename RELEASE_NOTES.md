# Logitech G HUB Profile Indicator 1.0.1

This update brings the animated glass-style indicator, automatic profile previews, startup controls and the drag-position fix together in one public release.

## Download and run

Download **Logitech-G-HUB-Profile-Indicator-Windows-x64.zip**, extract it, and run **GHubIndicator.exe**. Keep Logitech G HUB running in the background. Python and administrator rights are not required.

For an upgrade, quit the old indicator first and replace the EXE in its existing folder. The executable name, saved preferences and startup registration remain compatible.

## New since 1.0.0

- New name: **Logitech G HUB Profile Indicator**.
- Enable or disable **Start with Windows** from the menu.
- Compact G circle with a tiny profile name underneath.
- Smooth liquid-glass-inspired styling, translucent antialiased edges, reflections and soft shadows.
- Hover or click to expand for **10 seconds**.
- Profile changes automatically expand for **5 seconds**, then collapse; successive changes restart the preview.
- Your last dragged position stays fixed through opening and closing, including movement during animation and placement near monitor edges.
- Support for monitors left of or above the primary display.
- Existing read-only live detection, tray controls and optional change notifications are preserved.

## Detection and appearance limits

Reads the effective software profile directly from G HUB's verified private local interface. This is not an officially supported Logitech API, and future G HUB updates may require compatibility changes. Onboard hardware settings are not independently verified. Exclusive-fullscreen games may cover the overlay.

The glass finish is a custom alpha-transparent visual treatment, not Apple's system material or live desktop blur. The executable is unsigned.

Source, tests, setup/build instructions and license notices are available in the repository. SHA-256 checksums are attached to this release. This independent utility is not affiliated with or endorsed by Logitech.
