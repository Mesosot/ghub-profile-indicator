# Third-party runtime components

The Windows executable bundles Python 3.12.10 and its standard runtime libraries, Tcl/Tk 8.6, SQLite, OpenSSL and websocket-client 1.9.2. It is packaged with the PyInstaller 6.22.3 bootloader.

License texts are included under `licenses/`:

- Python and bundled runtime license notices: `Python.txt`.
- Tcl/Tk license: `Tk.txt` (the Python license collection also contains Tcl/Tk notices).
- websocket-client: `websocket-client.txt` (Apache License 2.0).
- PyInstaller: `PyInstaller.txt` (GPL with its bootloader distribution exception).

No G HUB or Logitech library binaries are redistributed. The program queries the user's installed G HUB agent on loopback. No GitHub project source was copied into this implementation.
