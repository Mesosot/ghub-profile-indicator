import unittest

from glass import GlassRenderer


class GlassTests(unittest.TestCase):
    def setUp(self):
        self.renderer = GlassRenderer()

    def test_compact_uses_transparent_corners_and_soft_alpha_edges(self):
        image = self.renderer.render(112, 68, 0, 'Desktop: Default', 'Live')
        self.assertEqual(image.mode, 'RGBA')
        self.assertEqual(image.size, (112, 68))
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertGreater(image.getpixel((56, 23))[3], 220)
        # Supersampled circle edges have partial pixel coverage, not a hard region cutout.
        alpha = image.getchannel('A')
        self.assertTrue(any(0 < alpha.getpixel((x, 8)) < 180 for x in range(30, 82)))

    def test_expanded_and_intermediate_sizes_render_long_unicode_names(self):
        for width, height, progress in [(380, 122, 1), (220, 90, 0.4)]:
            with self.subTest(width=width):
                image = self.renderer.render(width, height, progress,
                    'League of Legends: بروفايل جديد طويل جدًا', 'Live from G HUB')
                self.assertEqual(image.size, (width, height))
                self.assertGreater(image.getchannel('A').getextrema()[1], 230)


if __name__ == '__main__':
    unittest.main()
