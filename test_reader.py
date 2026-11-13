import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

from reader import Agent, ReadError, device_summary, parse_profile, read_catalog


class ReaderTests(unittest.TestCase):
    def test_live_wal_and_no_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings #1.db'
            conn = sqlite3.connect(path)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE data (_id INTEGER PRIMARY KEY, file BLOB)')
            conn.execute('INSERT INTO data VALUES(1, ?)', (json.dumps({
                'applications': {'applications': [{'applicationId': 'a', 'name': 'Old'}]}}),))
            conn.commit()
            conn.execute('UPDATE data SET file=?', (json.dumps({
                'applications': {'applications': [{'applicationId': 'a', 'name': 'New'}]}}),))
            conn.commit()
            self.assertEqual(read_catalog(path), {'a': 'New'})
            self.assertEqual(conn.execute('SELECT count(*) FROM data').fetchone()[0], 1)
            conn.close()

    def test_profile_comes_from_live_response_not_catalog_selection(self):
        result = parse_profile({'id': 'live', 'name': 'Tibia', 'applicationId': 'client'}, {'client': 'client'})
        self.assertEqual(result['label'], 'client: Tibia')
        self.assertEqual(result['id'], 'live')

    def test_localization_and_missing_catalog(self):
        value = {'id': 'p', 'name': 'PROFILE_NAME_DEFAULT', 'applicationId': 'a'}
        self.assertEqual(parse_profile(value, {'a': 'APPLICATION_NAME_DESKTOP'})['label'], 'Desktop: Default')
        self.assertEqual(parse_profile(value, {})['label'], 'Application a: Default')

    def test_missing_or_changed_schema_never_guesses(self):
        for value in [None, {}, {'id': 'x'}, {'id': 'x', 'name': [], 'applicationId': 'a'}]:
            with self.assertRaises(ReadError):
                parse_profile(value, {})

    def test_onboard_warning(self):
        count, onboard = device_summary({'deviceInfos': [
            {'state': 'ACTIVE', 'onboardMode': True, 'displayName': 'Mouse'},
            {'state': 'INACTIVE', 'onboardMode': False}]})
        self.assertEqual((count, onboard), (1, ['Mouse']))
        with self.assertRaises(ReadError):
            device_summary({})

    def test_mutating_or_unknown_endpoint_is_rejected_before_send(self):
        agent = Agent()
        agent.ws = Mock()
        for path in ['/profile/refresh', '/profile/import', '/mouse/dpi', '/anything']:
            with self.assertRaises(ReadError):
                agent.get(path)
        agent.ws.send.assert_not_called()

    def test_only_get_and_matching_successful_response(self):
        agent = Agent()
        ws = Mock()
        agent.ws = ws
        def receive():
            request = json.loads(ws.send.call_args.args[0])
            self.assertEqual(request['verb'], 'GET')
            return json.dumps({'msgId': request['msgId'], 'origin': 'backend',
                               'result': {'code': 'SUCCESS'}, 'payload': {'id': 'live'}})
        ws.recv.side_effect = receive
        self.assertEqual(agent.get('/profile/active'), {'id': 'live'})

    def test_rejected_query_is_unavailable(self):
        agent = Agent()
        agent.ws = Mock()
        def receive():
            request = json.loads(agent.ws.send.call_args.args[0])
            return json.dumps({'msgId': request['msgId'], 'origin': 'backend',
                               'result': {'code': 'INVALID_ARG'}})
        agent.ws.recv.side_effect = receive
        with self.assertRaises(ReadError):
            agent.get('/profile/effective')


if __name__ == '__main__':
    unittest.main()
