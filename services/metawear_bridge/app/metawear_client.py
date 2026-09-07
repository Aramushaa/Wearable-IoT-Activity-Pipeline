"""Small wrapper around the MbientLab MetaWear SDK.

The rest of the project should not need to know the C callback signatures used
by `libmetawear`; it only receives normalized `(sensor, timestamp, x, y, z)`
values through a Python callback.
"""

from mbientlab.metawear import MetaWear, libmetawear, parse_value
from mbientlab.metawear.cbindings import *
from time import sleep
from threading import Event
import traceback

import re

class MetaWearClient:
    """Connect to a MetaWear board and stream accelerometer/gyroscope data."""

    def __init__(self, mac_address):
        """Prepare SDK callbacks and keep the board MAC address."""
        self.mac_address = mac_address
        self.stop_sampling_event = Event()
        self.r = re.compile("[+-]?[0-9]*[.][0-9]+")
        self.cb = self.default_callback
        self.accCallback = FnVoid_VoidP_DataP(self.acc_data_handler)
        self.gyroCallback = FnVoid_VoidP_DataP(self.gyro_data_handler)

    def acc_data_handler(self, ctx, data):
        """Handle one accelerometer notification from the vendor SDK."""
        axis_values = self.r.findall(str(parse_value(data)))
        if len(axis_values) < 3:
            print("Invalid MetaWear ACC parse:", parse_value(data))
            return
        self.cb('acc',data.contents.epoch, axis_values[0], axis_values[1], axis_values[2])

    def gyro_data_handler(self, ctx, data):
        """Handle one gyroscope notification from the vendor SDK."""
        axis_values = self.r.findall(str(parse_value(data)))
        if len(axis_values) < 3:
            print("Invalid MetaWear GYRO parse:", parse_value(data))
            return
        self.cb('gyro',data.contents.epoch, axis_values[0], axis_values[1], axis_values[2])

    def default_callback(self, sensor, timestamp, x, y, z):
        """Fallback callback used before the bridge installs its publisher."""
        print("[" + sensor.upper() + "]: (" + str(timestamp) + ") " + str(x) + " - " + str(y) + " - " + str(z))

    def set_callback(self, callback_fn):
        """Install the callback that receives normalized sensor samples."""
        self.cb = callback_fn

    def stop_sampling(self, signum='', frame=''):
        """Signal the blocking sampling loop to exit."""
        self.stop_sampling_event.set()

    def connect(self):
        """Connect to the MetaWear board over BLE or USB."""
        self.d = MetaWear(self.mac_address)
        connected = False
        while not connected:
            try:
                self.d.connect()
            except Exception as e:
                print("Connection failed.")
                print("ERROR TYPE:", type(e).__name__)
                print("ERROR MESSAGE:", str(e))
                traceback.print_exc()
                raise
            else:
                connected = True
        print("Connected to " + self.d.address + " over " + ("USB" if self.d.usb.is_connected else "BLE"))

    def configure(self):
        """Configure 25 Hz accelerometer and gyroscope streaming."""
        libmetawear.mbl_mw_settings_set_connection_parameters(self.d.board, 7.5, 7.5, 0, 6000)
        sleep(1.5)
        libmetawear.mbl_mw_acc_bmi270_set_odr(self.d.board, AccBmi270Odr._25Hz)
        libmetawear.mbl_mw_acc_bosch_set_range(self.d.board, AccBoschRange._4G)
        libmetawear.mbl_mw_acc_write_acceleration_config(self.d.board)
        libmetawear.mbl_mw_gyro_bmi270_set_range(self.d.board, GyroBoschRange._1000dps)
        libmetawear.mbl_mw_gyro_bmi270_set_odr(self.d.board, GyroBoschOdr._25Hz)
        libmetawear.mbl_mw_gyro_bmi270_write_config(self.d.board)

        acc = libmetawear.mbl_mw_acc_get_acceleration_data_signal(self.d.board)
        libmetawear.mbl_mw_datasignal_subscribe(acc, None, self.accCallback)
        gyro = libmetawear.mbl_mw_gyro_bmi270_get_rotation_data_signal(self.d.board)
        libmetawear.mbl_mw_datasignal_subscribe(gyro, None, self.gyroCallback)

    def start_sampling(self):
        """Enable both sensors and block until `stop_sampling` is called."""
        libmetawear.mbl_mw_acc_enable_acceleration_sampling(self.d.board)
        libmetawear.mbl_mw_acc_start(self.d.board)
        libmetawear.mbl_mw_gyro_bmi270_enable_rotation_sampling(self.d.board)
        libmetawear.mbl_mw_gyro_bmi270_start(self.d.board)

        while not self.stop_sampling_event.is_set():
            sleep(1)

    def disconnect(self):
        """Stop sensors, unsubscribe callbacks, and disconnect the board."""
        libmetawear.mbl_mw_acc_stop(self.d.board)
        libmetawear.mbl_mw_acc_disable_acceleration_sampling(self.d.board)

        libmetawear.mbl_mw_gyro_bmi270_stop(self.d.board)
        libmetawear.mbl_mw_gyro_bmi270_disable_rotation_sampling(self.d.board)

        acc = libmetawear.mbl_mw_acc_get_acceleration_data_signal(self.d.board)
        libmetawear.mbl_mw_datasignal_unsubscribe(acc)

        gyro = libmetawear.mbl_mw_gyro_bmi270_get_rotation_data_signal(self.d.board)
        libmetawear.mbl_mw_datasignal_unsubscribe(gyro)

        libmetawear.mbl_mw_debug_disconnect(self.d.board)





