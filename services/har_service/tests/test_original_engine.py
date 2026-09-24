"""Regression checks derived from the user-supplied original engine."""
import unittest
import numpy as np
from model.inference_engine import InferenceEngine, softmax


class OriginalEngineTests(unittest.TestCase):
    def engine(self):
        return InferenceEngine('unused', ['a', 'b'], score_aggregation='original')

    def test_original_3d_output_uses_first_outer_slice(self):
        # Later timesteps favor b; the supplied original still selects a.
        scores = np.array([[[3., 1.]], [[0., 100.]]])
        np.testing.assert_array_equal(self.engine()._aggregate_scores(scores), [3., 1.])

    def test_original_2d_output_sums_rows(self):
        np.testing.assert_array_equal(self.engine()._aggregate_scores(np.array([[3.,1.],[2.,4.]])), [5.,5.])

    def test_original_1d_output_is_unchanged(self):
        np.testing.assert_array_equal(self.engine()._aggregate_scores(np.array([3.,1.])), [3.,1.])

    def test_original_tensor_preserves_raw_acceleration_then_gyro(self):
        tensor=self.engine()._build_input_tensor(
            dict(x=[1,2],y=[3,4],z=[5,6]),
            dict(x=[7,8],y=[9,10],z=[11,12]))
        np.testing.assert_array_equal(tensor, [[[1,3,5,7,9,11]],[[2,4,6,8,10,12]]])
        self.assertEqual(tensor.dtype, np.float32)

    def test_full_sequence_sum_remains_an_explicit_alternative(self):
        engine=InferenceEngine('unused',['a','b'],score_aggregation='sum')
        np.testing.assert_array_equal(engine._aggregate_scores(np.array([[[3.,1.]],[[0.,100.]]])), [3.,101.])

if __name__ == '__main__':
    unittest.main()
