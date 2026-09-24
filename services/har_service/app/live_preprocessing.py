"""Adapt left-wrist MetaWear rows to the model's live input contract.

The axis mapping was selected from the 24 proper 3D rotations using labeled
left-wrist typing and writing trials. Only live inference uses this adapter;
stored sensor rows remain unchanged.
"""
import math


class WatchPreprocessor:
    """Convert units and interpolate one stream onto a 20 Hz time grid."""

    def __init__(self):
        self.previous = None
        self.origin = 0.0
        self.index = 0

    def push(self, row):
        current = dict(row)
        t = float(row['dataset_ts'])
        values = [float(row[f'{sensor}_{axis}'])
                  for sensor in ('acc', 'gyro') for axis in 'xyz']
        if not all(math.isfinite(v) for v in [t, *values]):
            raise ValueError('Non-finite watch timestamp or sensor value')
        # The board is rotated 90 degrees relative to the model's coordinate
        # frame: model X=-watch Y, model Y=watch X, model Z=watch Z.
        current['acc_x'] = -float(row['acc_y']) * 9.80665
        current['acc_y'] = float(row['acc_x']) * 9.80665
        current['acc_z'] = float(row['acc_z']) * 9.80665
        current['gyro_x'] = -math.radians(float(row['gyro_y']))
        current['gyro_y'] = math.radians(float(row['gyro_x']))
        current['gyro_z'] = math.radians(float(row['gyro_z']))
        current['dataset_ts'] = t
        current['sampling_rate_hz'] = 20.0
        previous = self.previous
        reset = previous is None or t < previous['dataset_ts'] or t - previous['dataset_ts'] > .25
        if reset:
            self.previous = current
            self.origin = t
            self.index = 1
            current['sample_idx'] = 0
            return [current], True
        if t == previous['dataset_ts']:
            return [], False
        output = []
        target = self.origin + self.index / 20.0
        while target <= t + 1e-9:
            fraction = min(1.0, (target - previous['dataset_ts']) / (t - previous['dataset_ts']))
            interpolated = dict(current)
            for sensor in ('acc', 'gyro'):
                for axis in 'xyz':
                    key = f'{sensor}_{axis}'
                    interpolated[key] = previous[key] + fraction * (current[key] - previous[key])
            interpolated['dataset_ts'] = target
            interpolated['sample_idx'] = self.index
            output.append(interpolated)
            self.index += 1
            target = self.origin + self.index / 20.0
        self.previous = current
        return output, False
