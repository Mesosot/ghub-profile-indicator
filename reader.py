"""Read-only, verified G HUB local-agent queries. No profile inference."""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import time
import uuid

import websocket

ALLOWED = frozenset(('/profile/active', '/profile/effective', '/devices/list'))
DEFAULT_DB = Path(os.environ.get('LOCALAPPDATA', '.')) / 'LGHUB' / 'settings.db'


class ReadError(Exception):
    pass


def read_catalog(path=DEFAULT_DB):
    """Use SQLite's live WAL reader, never immutable=1 or a torn file copy."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro',
                                 uri=True, timeout=0.2)) as conn:
        conn.execute('PRAGMA query_only=ON')
        row = conn.execute('SELECT file FROM data ORDER BY _id DESC LIMIT 1').fetchone()
        if not row:
            raise ReadError('G HUB settings contain no data')
        data = json.loads(row[0])
    apps = data.get('applications', {}).get('applications')
    if not isinstance(apps, list):
        raise ReadError('Unrecognized G HUB application catalog')
    return {a['applicationId']: a.get('name', '') for a in apps
            if isinstance(a, dict) and isinstance(a.get('applicationId'), str)}


def friendly(name):
    return {'APPLICATION_NAME_DESKTOP': 'Desktop',
            'PROFILE_NAME_DEFAULT': 'Default'}.get(name, name)


def parse_profile(payload, catalog):
    if not isinstance(payload, dict):
        raise ReadError('Unrecognized profile response')
    pid, name, aid = (payload.get(k) for k in ('id', 'name', 'applicationId'))
    if not all(isinstance(s, str) and s for s in (pid, name, aid)):
        raise ReadError('G HUB did not report a complete effective profile')
    app = friendly(catalog.get(aid, 'Application ' + aid[:8]))
    return {'id': pid, 'application_id': aid, 'app': app,
            'profile': friendly(name), 'label': app + ': ' + friendly(name)}


class Agent:
    def __init__(self, port=9010):
        self.port = port
        self.ws = None

    def connect(self):
        # Fixed loopback host. Explicitly bypass proxy settings; never contact a remote host.
        self.ws = websocket.create_connection(
            f'ws://127.0.0.1:{self.port}', origin='file://', subprotocols=['json'],
            timeout=1.5, http_no_proxy=['127.0.0.1', 'localhost'])

    def get(self, path):
        if path not in ALLOWED:
            raise ReadError('Query is not on the read-only allowlist')
        if self.ws is None:
            self.connect()
        mid = str(uuid.uuid4())
        self.ws.send(json.dumps({'msgId': mid, 'verb': 'GET', 'path': path}))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            raw = self.ws.recv()
            if not raw:
                raise ReadError('G HUB closed the connection')
            message = json.loads(raw)
            if not isinstance(message, dict) or message.get('msgId') != mid:
                continue
            if message.get('result', {}).get('code') != 'SUCCESS':
                raise ReadError('G HUB rejected ' + path)
            if message.get('origin') != 'backend':
                raise ReadError('Unexpected response origin')
            return message.get('payload')
        raise ReadError('G HUB response timed out')

    def close(self):
        if self.ws is not None:
            try:
                self.ws.close(timeout=0)
            except Exception:
                pass
            self.ws = None


def device_summary(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('deviceInfos'), list):
        raise ReadError('Unrecognized device state')
    devices = payload['deviceInfos']
    active = [d for d in devices if d.get('state') == 'ACTIVE']
    onboard = [d.get('displayName', 'Device') for d in active if d.get('onboardMode')]
    return len(active), onboard


def sample(agent, catalog):
    # Read the effective profile straight from the agent. DB supplies ONLY app display names.
    profile = parse_profile(agent.get('/profile/effective'), catalog)
    count, onboard = device_summary(agent.get('/devices/list'))
    profile.update(device_count=count, onboard=onboard)
    return profile
