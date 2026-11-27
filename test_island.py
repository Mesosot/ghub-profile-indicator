"""Windows UI checks with a short test timeout; no G HUB or startup writes."""
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app


class IslandTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patches = [patch.object(app, 'HOME', Path(self.folder.name)),
                        patch.object(app, 'CONFIG', Path(self.folder.name)/'config.json'),
                        patch.object(app.Indicator, 'worker'),
                        patch.object(app.threading, 'Thread'),
                        patch.object(app, 'load_config', return_value={'tray': False, 'x': 600, 'y': 250}),
                        patch.object(app, 'COLLAPSE_DELAY_MS', 900),
                        patch.object(app, 'PROFILE_CHANGE_DELAY_MS', 450)]
        for item in self.patches:
            item.start()
        self.ui = app.Indicator(SimpleNamespace(port=9010, db=app.DEFAULT_DB,
                                               qa_window=True, smoke_seconds=0))
        self.ui.hover_locked = True
        self.ui.root.update()

    def tearDown(self):
        self.ui.quit()
        self.ui = None
        for item in reversed(self.patches):
            item.stop()
        import gc
        gc.collect()
        self.folder.cleanup()

    def settle(self, seconds=0.43):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            self.ui.root.update()
            time.sleep(0.005)

    def test_hover_opens_then_timeout_closes(self):
        self.assertEqual(self.ui.island_size, app.COMPACT_DIMENSIONS)
        self.ui.hover_locked = False
        self.ui.hover_expand()
        self.settle()
        self.assertTrue(self.ui.expanded)
        self.assertEqual(self.ui.island_size, (380, 122))
        self.settle(1.0)
        self.assertFalse(self.ui.expanded)
        self.assertEqual(self.ui.island_size, app.COMPACT_DIMENSIONS)

    def test_click_opens_and_rapid_reversal_finishes_cleanly(self):
        event = SimpleNamespace(x_root=610, y_root=260)
        self.ui.start_drag(event)
        self.ui.end_drag(event)
        self.assertTrue(self.ui.expanded)
        self.settle(0.08)
        self.ui.collapse()
        self.settle(0.08)
        self.ui.expand()
        self.settle()
        self.assertTrue(self.ui.expanded)
        self.assertFalse(self.ui.animating)
        self.assertEqual(self.ui.island_size, (380, 122))

    def test_drag_does_not_count_as_click(self):
        self.ui.start_drag(SimpleNamespace(x_root=610, y_root=260))
        event = SimpleNamespace(x_root=710, y_root=310)
        self.ui.move_drag(event)
        self.ui.end_drag(event)
        self.settle(0.04)
        self.assertFalse(self.ui.expanded)
        self.assertEqual(self.ui.root.winfo_x()+(app.COMPACT_DIMENSIONS[0]-app.COMPACT_SIZE)//2, 700)

    def test_collapse_cancels_old_timer_and_waits_for_menu(self):
        self.ui.expand()
        self.settle()
        old_timer = self.ui.collapse_job
        self.ui.menu_open = True
        self.ui.collapse()
        self.assertTrue(self.ui.expanded)
        self.assertNotEqual(self.ui.collapse_job, old_timer)
        self.ui.menu_open = False
        self.ui.collapse()
        self.settle()
        self.assertFalse(self.ui.expanded)
        self.assertIsNone(self.ui.collapse_job)

    def test_compact_position_persists_across_expansion(self):
        self.ui.expand()
        self.settle()
        self.ui.save()
        import json
        saved = json.loads(app.CONFIG.read_text())
        self.assertEqual(saved['x'], 600)
        self.ui.collapse()
        self.settle()
        self.assertEqual(self.ui.root.winfo_x()+(app.COMPACT_DIMENSIONS[0]-app.COMPACT_SIZE)//2, 600)

    def drag_by(self, dx, dy):
        x, y = self.ui.window_position
        start = SimpleNamespace(x_root=x+20, y_root=y+20)
        end = SimpleNamespace(x_root=x+20+dx, y_root=y+20+dy)
        self.ui.start_drag(start)
        self.ui.move_drag(end)
        # Release before Tk has processed the geometry request: this used to jump back.
        self.ui.end_drag(end)

    def test_drag_expanded_returns_to_new_anchor_without_processing_geometry_first(self):
        self.ui.expand()
        self.settle()
        self.drag_by(140, 70)
        expected = self.ui.compact_anchor
        self.assertEqual(expected, (740, 320))
        self.ui.collapse()
        self.settle()
        self.assertEqual(self.ui.window_position, self.ui.position_for_size(*app.COMPACT_DIMENSIONS))
        self.assertEqual(self.ui.compact_anchor, expected)
        import json
        self.assertEqual(json.loads(app.CONFIG.read_text())['x'], expected[0])

    def test_drag_during_expansion_stays_at_new_position_on_repeated_cycles(self):
        self.ui.expand()
        self.settle(0.08)
        self.drag_by(90, 40)
        expected = self.ui.compact_anchor
        self.settle()
        for _ in range(2):
            self.ui.collapse()
            self.settle()
            self.assertEqual(self.ui.compact_anchor, expected)
            self.assertEqual(self.ui.window_position, self.ui.position_for_size(*app.COMPACT_DIMENSIONS))
            self.ui.expand()
            self.settle()

    def test_expansion_at_screen_edges_does_not_overwrite_compact_anchor(self):
        for anchor in [(33, 20), (self.ui.root.winfo_screenwidth()-79,
                                   self.ui.root.winfo_screenheight()-68)]:
            self.ui.collapse()
            self.settle()
            self.ui.compact_anchor = anchor
            self.ui.window_position = self.ui.position_for_size(*app.COMPACT_DIMENSIONS)
            self.ui.expand()
            self.settle()
            self.ui.collapse()
            self.settle()
            self.assertEqual(self.ui.compact_anchor, anchor)
            self.assertEqual(self.ui.window_position, self.ui.position_for_size(*app.COMPACT_DIMENSIONS))

    @patch.object(app, 'desktop_work_area', return_value=(-1080, -200, 0, 1680))
    def test_negative_monitor_drag_keeps_anchor_after_expand_and_collapse(self, area):
        self.drag_by(-1100, -350)
        expected = self.ui.compact_anchor
        self.assertLess(expected[0], 0)
        self.assertLess(expected[1], 0)
        self.ui.expand()
        self.settle()
        self.ui.collapse()
        self.settle()
        self.assertEqual(self.ui.compact_anchor, expected)
        self.assertEqual(self.ui.window_position, self.ui.position_for_size(*app.COMPACT_DIMENSIONS))
        self.assertLess(self.ui.window_position[0], 0)
        self.assertEqual((self.ui.root.winfo_x(), self.ui.root.winfo_y()), self.ui.window_position)

    def send_profile(self, ident, label):
        self.ui.emit(('profile', {'id': ident, 'label': label, 'device_count': 1,
                                 'onboard': []}, time.monotonic()))
        self.settle(0.13)

    def test_caption_updates_and_real_change_opens_then_collapses(self):
        self.send_profile('desktop', 'Desktop: Default')
        self.assertFalse(self.ui.expanded)
        self.assertEqual(self.ui.compact_caption.cget('text'), 'Desktop: Default')
        self.send_profile('game', 'client: Tibia')
        self.assertTrue(self.ui.expanded)
        self.assertEqual(self.ui.label.cget('text'), 'client: Tibia')
        self.assertEqual(self.ui.compact_caption.cget('text'), 'client: Tibia')
        self.assertEqual(self.ui.collapse_delay_ms, 450)
        self.settle(0.8)
        self.assertFalse(self.ui.expanded)
        self.assertEqual(self.ui.island_size, app.COMPACT_DIMENSIONS)

    @patch.object(app, 'PROFILE_CHANGE_DELAY_MS', 2000)
    def test_same_id_does_not_reopen_and_latest_change_replaces_timer(self):
        self.send_profile('a', 'Desktop: Default')
        self.send_profile('b', 'Game: One')
        first_job = self.ui.collapse_job
        self.send_profile('b', 'Game: One')
        self.assertEqual(self.ui.collapse_job, first_job)
        self.send_profile('c', 'Game: Two')
        self.assertNotEqual(self.ui.collapse_job, first_job)
        self.assertEqual(self.ui.compact_caption.cget('text'), 'Game: Two')
        self.ui.expand()
        self.assertEqual(self.ui.collapse_delay_ms, 900)

    def test_hidden_overlay_stays_hidden_and_error_clears_caption(self):
        self.send_profile('a', 'Desktop: Default')
        self.ui.hidden = True
        self.send_profile('b', 'client: Tibia')
        self.assertFalse(self.ui.expanded)
        self.assertEqual(self.ui.compact_caption.cget('text'), 'client: Tibia')
        self.ui.emit(('error', 'Disconnected', time.monotonic()))
        self.settle(0.13)
        self.assertEqual(self.ui.compact_caption.cget('text'), 'Unavailable')

    def test_long_caption_is_measured_and_full_name_remains_available(self):
        name = 'League of Legends: A very long named profile'
        self.send_profile('lol', name)
        short = self.ui.compact_caption.cget('text')
        self.assertTrue(short.endswith('…'))
        self.assertLessEqual(self.ui.caption_font.measure(short), app.COMPACT_DIMENSIONS[0]-10)
        self.assertEqual(self.ui.label.cget('text'), name)

    def test_change_during_menu_is_deferred_until_menu_closes(self):
        self.send_profile('a', 'Desktop: Default')
        self.ui.menu_open = True
        self.send_profile('b', 'client: Tibia')
        self.assertFalse(self.ui.expanded)
        self.assertTrue(self.ui.profile_change_pending)
        self.ui.menu_closed()
        self.assertTrue(self.ui.expanded)
        self.assertFalse(self.ui.profile_change_pending)
        self.assertEqual(self.ui.collapse_delay_ms, 450)


if __name__ == '__main__':
    unittest.main()
