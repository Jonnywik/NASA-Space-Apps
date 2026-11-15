import tempfile
import unittest
from pathlib import Path

from processing.places import gazetteer
from test_places_support import make_places_root, MID_LON, MID_LAT, W, N


class GazetteerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_places_root(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def names(self, q, limit=10):
        return [(r['id']) for r in gazetteer.search(q, limit, root=self.root)]

    def test_normalize(self):
        self.assertEqual(gazetteer.normalize('Brgy. Niño'), 'nino')
        self.assertEqual(gazetteer.normalize('Barangay 28'), '28')
        self.assertEqual(gazetteer.normalize('City of Malabon'), 'malabon')
        self.assertEqual(gazetteer.normalize('BRGY Peña  Bayan'), 'pena bayan')

    def test_prefix_and_diacritics(self):
        self.assertEqual(self.names('Brgy. Nino'), ['T1-1'])
        self.assertEqual(self.names('barangay NIÑO'), ['T1-1'])
        self.assertEqual(self.names('test ni'), ['T1-1'])

    def test_substring_and_ranking(self):
        # exact-prefix matches come before substring matches
        self.assertEqual(self.names('test poblacion')[:2], ['T1-2', 'T2-1'])
        self.assertIn('T2-2', self.names('barangay 28'))
        self.assertIn('T2-2', self.names('gay'))

    def test_city_search_and_limit(self):
        res = gazetteer.search('beta', 5, root=self.root)
        self.assertEqual(res[0]['id'], 'T2')
        self.assertEqual(res[0]['level'], 'city')
        self.assertEqual(len(gazetteer.search('test', 3, root=self.root)), 3)

    def test_result_shape_and_empty(self):
        r = gazetteer.search('niño', root=self.root)[0]
        for k in ('id', 'name', 'level', 'city', 'province', 'lon', 'lat', 'bbox'):
            self.assertIn(k, r)
        self.assertEqual(gazetteer.search('   ', root=self.root), [])
        self.assertEqual(gazetteer.search('zzzzqq', root=self.root), [])

    def test_point_lookup(self):
        r = gazetteer.locate(W + 0.001, N - 0.001, root=self.root)
        self.assertEqual(r['barangay']['id'], 'T1-1')
        self.assertEqual(r['city']['id'], 'T1')
        r = gazetteer.locate(MID_LON + 0.001, MID_LAT - 0.001, root=self.root)
        self.assertEqual((r['barangay']['id'], r['city']['name']), ('T2-2', 'Test City Beta'))
        r = gazetteer.locate(120.5, 14.0, root=self.root)
        self.assertIsNone(r['barangay'])
        self.assertIsNone(r['city'])


if __name__ == '__main__':
    unittest.main()
