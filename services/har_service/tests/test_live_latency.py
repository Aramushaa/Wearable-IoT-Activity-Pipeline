import unittest
from collections import deque
from threading import Event, Thread
from unittest.mock import patch

from app.config import settings
from app.mqtt_stream import LiveHarMqttService


class LiveWindowCadenceTests(unittest.TestCase):
    def test_live_window_runs_after_every_new_sample(self):
        service = LiveHarMqttService.__new__(LiveHarMqttService)
        service.buffers = {}
        windows = []
        service.evaluate_window = lambda window: windows.append(list(window))

        settings.__dict__["live_window_stride"] = 1
        try:
            with patch.object(settings, "window_size", 3):
                for sample_idx in range(5):
                    service._add_prepared_row(
                        ("watch", "trial"),
                        {"sample_idx": sample_idx},
                    )
        finally:
            settings.__dict__.pop("live_window_stride", None)

        self.assertEqual(
            [[row["sample_idx"] for row in window] for window in windows],
            [[0, 1, 2], [1, 2, 3], [2, 3, 4]],
        )
        self.assertEqual(
            [row["sample_idx"] for row in service.buffers[("watch", "trial")]],
            [3, 4],
        )

    def test_influx_write_does_not_block_live_prediction(self):
        write_started = Event()
        release_write = Event()
        mqtt_published = Event()

        def blocking_write(**kwargs):
            write_started.set()
            release_write.wait(2)

        class FakeInference:
            def predict_details(self, model_input):
                return {"predicted_label": "typing", "confidence": 90.0}

        class FakePublisher:
            def publish(self, payload):
                mqtt_published.set()

        service = LiveHarMqttService.__new__(LiveHarMqttService)
        service.inference = FakeInference()
        service.prediction_publisher = FakePublisher()
        row = {
            "source": "metawear",
            "device": "watch",
            "recording_id": "trial",
            "activity_gt": "typing",
            "dataset_ts": 1.0,
            "sample_idx": 1,
            "acc_x": 0.0,
            "acc_y": 0.0,
            "acc_z": 9.8,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
        }

        with patch("app.mqtt_stream.write_prediction_point", blocking_write):
            inference_thread = Thread(target=service.evaluate_window, args=([row],))
            inference_thread.start()
            self.assertTrue(write_started.wait(1))
            inference_thread.join(0.1)
            returned_without_database = not inference_thread.is_alive()
            release_write.set()
            inference_thread.join(1)

        self.assertTrue(returned_without_database)
        self.assertTrue(mqtt_published.is_set())


if __name__ == "__main__":
    unittest.main()
