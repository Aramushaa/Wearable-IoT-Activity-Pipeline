import unittest
from app.live_preprocessing import WatchPreprocessor


def sample(t, **values):
    return dict(device='watch', recording_id='test', source='metawear',
                dataset_ts=t, sample_idx=0, acc_x=1., acc_y=0., acc_z=-1.,
                gyro_x=180., gyro_y=0., gyro_z=-90., **values)


class WatchPreprocessingTests(unittest.TestCase):
    def test_rotates_left_wrist_axes_and_converts_to_si_units(self):
        original = sample(0)
        rows, _ = WatchPreprocessor().push(original)
        self.assertAlmostEqual(rows[0]['acc_x'], 0.0)
        self.assertAlmostEqual(rows[0]['acc_y'], 9.80665)
        self.assertAlmostEqual(rows[0]['acc_z'], -9.80665)
        self.assertAlmostEqual(rows[0]['gyro_x'], 0.0)
        self.assertAlmostEqual(rows[0]['gyro_y'], 3.141592653589793)
        self.assertAlmostEqual(rows[0]['gyro_z'], -1.5707963267948966)
        self.assertEqual(original['acc_x'], 1.)

    def test_25hz_samples_produce_20hz_two_second_window(self):
        p = WatchPreprocessor()
        rows = []
        for i in range(51):
            out, _ = p.push(sample(i * .04))
            rows.extend(out)
        self.assertEqual(len(rows), 41)
        self.assertAlmostEqual(rows[39]['dataset_ts'], 1.95)
        self.assertAlmostEqual(rows[-1]['dataset_ts'], 2.)

    def test_interpolates_between_samples(self):
        p = WatchPreprocessor()
        p.push(sample(0))
        r = sample(.04); r['gyro_y'] = 40
        p.push(r)
        r = sample(.08); r['gyro_y'] = 80
        rows, _ = p.push(r)
        self.assertAlmostEqual(rows[0]['dataset_ts'], .05)
        self.assertAlmostEqual(rows[0]['gyro_x'], -.8726646259971648)

    def test_gap_or_restart_resets_instead_of_fabricating_samples(self):
        p = WatchPreprocessor()
        p.push(sample(0))
        rows, reset = p.push(sample(10))
        self.assertTrue(reset)
        self.assertEqual(len(rows), 1)
        rows, reset = p.push(sample(0))
        self.assertTrue(reset)
        self.assertEqual(len(rows), 1)

    def test_duplicate_and_invalid_samples_do_not_corrupt_state(self):
        p = WatchPreprocessor()
        p.push(sample(0))
        self.assertEqual(p.push(sample(0)), ([], False))
        bad = sample(.04); bad['acc_x'] = float('nan')
        with self.assertRaises(ValueError):
            p.push(bad)
        rows, reset = p.push(sample(.05))
        self.assertFalse(reset)
        self.assertEqual(len(rows), 1)

if __name__ == '__main__':
    unittest.main()
