# Contributing

Bug reports and pull requests are welcome. For a detection issue, include your Windows version, G HUB version, and the error shown under **Connection details / limitations**. Remove personal information before sharing diagnostic reports. Do not upload your G HUB settings database, macros, or device serial numbers.

Keep detection read-only. Do not add foreground-app guesses as an invisible fallback. Add meaningful reader tests for changes to response parsing.

Run tests with `python -m unittest discover -s . -v`. Build the Windows executable using `build.ps1`.
