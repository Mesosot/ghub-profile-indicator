# Third-party runtime components

The Windows executable bundles Python 3.12.10 and its standard runtime libraries, Tcl/Tk 8.6, SQLite, OpenSSL, websocket-client 1.9.2 and Pillow 11.3.0 with its wheel runtime libraries. It is packaged with the PyInstaller 6.22.3 bootloader. Segoe UI is read from the user's Windows font installation and is not redistributed.

License texts are included under `licenses/`:

- Python and bundled runtime license notices: `Python.txt`.
- Tcl/Tk license: `Tk.txt` (the Python license collection also contains Tcl/Tk notices).
- websocket-client: `websocket-client.txt` (Apache License 2.0).
- PyInstaller: `PyInstaller.txt` (GPL with its bootloader distribution exception).
- Pillow and its wheel dependency notices: the `Pillow/` directory (MIT-CMU and bundled component licenses).

No G HUB or Logitech library binaries are redistributed. The program queries the user's installed G HUB agent on loopback. No GitHub project source was copied into this implementation.
