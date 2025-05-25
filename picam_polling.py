"""
Created on May 06, 2025

@author: Benedikt Ursprung
"""

import time

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from ScopeFoundry import Measurement
from ScopeFoundryHW.picam.picam import PiCAM
from ScopeFoundryHW.picam.picam_hw import PicamHW


class PicamPolling(Measurement):

    name = "polling"

    def setup(self):
        """
        Runs once during app initialization.
        This is where you define your settings,
        and set up data structures.
        """
        s = self.settings
        s.New("save_h5", bool, initial=True)
        s.New("N", int, vmin=4, initial=10, description="Number of Readouts")
        s.New("hw", str, choices=[])

        # data structure of the measurement
        self.data = {
            "raw": np.linspace(0, 1, num=10 * 1024 * 400).reshape((10, 1024, 400)),
        }

    def run(self):
        self.do_polling()

        if self.settings["save_h5"]:
            self.save_h5(data=self.data)

    def prepare_hw(self, hw: PicamHW):
        hw.settings["ReadoutCount"] = self.settings["N"]
        hw.settings["ShutterTimingMode"] = "AlwaysOpen"
        hw.settings["TriggerResponse"] = "ReadoutPerTrigger"

    def do_polling(self):
        """populates self.data["raw"]"""
        s = self.settings
        hw: PicamHW = self.app.hardware[s["hw"]]
        cam: PiCAM = hw.cam

        self.prepare_hw(hw)
        
        cam.commit_parameters()

        committed = cam.are_parameters_committed()
        if not committed:
            arr = cam.commit_parameters()
            if arr:
                print(self.name, "failed to committed some parameters:", arr)
                return

        cam.init_polling()
        cam.start_acquisition()

        imshape = hw.get_shape()
        data_shape = (s["N"], *imshape)
        raw = self.data["raw"] = np.ones(data_shape, dtype=np.uint16) * 500

        t0 = time.perf_counter_ns()
        counts = 0
        running = True
        while running:
            if self.interrupt_measurement_called:
                cam.stop_acquisition()

            running, new_counts = cam.wait_for_acquisition_update()
            counts += new_counts
            if running:
                raw[counts : counts + new_counts] = cam.get_shaped_polled_data(imshape)
            self.set_progress(100.0 * (counts) / s["N"])

        cam.stop_acquisition()

        ms = (time.perf_counter_ns() - t0) / 1e6 / counts
        print(ms, "ms per frame with N =", counts)
        print(1000 / ms, "Hz")

    def setup_figure(self):

        self.cb_layout = cb_layout = QtWidgets.QHBoxLayout()
        cb_layout.addWidget(
            self.settings.New_UI(
                exclude=("activation", "run_state", "profile", "progress")
            )
        )

        hw_choices = {
            hw.name: hw for hw in self.app.hardware.values() if isinstance(hw, PicamHW)
        }

        self.hw_widgets = {}
        for name, hw in hw_choices.items():
            widget = QtWidgets.QGroupBox()
            widget.setTitle(name)
            widget.setFlat(False)
            l = QtWidgets.QHBoxLayout(widget)
            l.addWidget(hw.operations.new_button("Read from\nHardware"))
            l.addWidget(
                hw.settings.New_UI(
                    ("ExposureTime", "VerticalShiftRate", "FrameRateCalculation")
                )
            )
            l.addWidget(hw.settings.New_UI(("roi_x", "roi_w", "roi_x_bin")))
            l.addWidget(hw.settings.New_UI(("roi_y", "roi_h", "roi_y_bin")))
            self.hw_widgets[name] = widget
            widget.setVisible(False)
            cb_layout.addWidget(widget)

        self.settings.get_lq("hw").change_choice_list(hw_choices.keys())
        self.settings.get_lq("hw").add_listener(self.on_change_hw)
        self.on_change_hw()

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.new_start_stop_button())

        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QVBoxLayout(header_widget)
        header_layout.addLayout(cb_layout)
        header_layout.addLayout(btn_layout)

        # plot
        self.graphics_widget = self.setup_plot()

        # ScopeFoundry assumes .ui is the main widget:
        self.ui = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.ui.addWidget(header_widget)
        self.ui.addWidget(self.graphics_widget)

    def setup_plot(self):
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.axes = self.graphics_widget.addPlot(title=self.name)
        self.line = self.axes.plot(pen="r")
        return self.graphics_widget

    def update_display(self):
        raw = self.data["raw"]
        self.line.setData(raw.mean((0, 2)))

    def on_change_hw(self):
        for key, widget in self.hw_widgets.items():
            widget.setVisible(key == self.settings["hw"])

    # def do_polling_wait_for_trig(self):
    #     # mimiks rate_for_trig cpp example
    #     s = self.settings
    #     hw: PicamHW = self.app.hardware[s["device"]]
    #     cam: PiCAM = hw.cam

    #     readout_stride = cam.read_param("ReadoutStride")

    #     hw.settings["TriggerResponse"] = "ReadoutPerTrigger"
    #     hw.settings["TriggerDetermination"] = "NegativePolarity"

    #     committed = cam.are_parameters_committed()
    #     if not committed:
    #         print(cam.commit_parameters())

    #     t0 = time.perf_counter_ns()

    #     N = 100
    #     for i in range(N):
    #         d = cam.acquire(10, -1)
    #         print(d.shape)

    #     ms = (time.perf_counter_ns() - t0) / 1e6 / s["N"]
    #     print(
    #         ms,
    #         "ms per frame with N =",
    #         s["N"],
    #     )
    #     print(1000 / ms, "Hz")

    # ---------------------------------------------------------------------------
    # # UNCOMMENT IF YOU HAVE SCOPEFOUNDRY 2.0 OR EARLIER
    # ---------------------------------------------------------------------------

    def save_h5(self, data):
        self.open_new_h5_file(data)
        self.close_h5_file()

    def open_new_h5_file(self, data):
        self.close_h5_file()

        from ScopeFoundry import h5_io

        self.h5_file = h5_io.h5_base_file(self.app, measurement=self)
        self.h5_meas_group = h5_io.h5_create_measurement_group(self, self.h5_file)

        for name, v in data.items():
            self.h5_meas_group[name] = v

        return self.h5_meas_group

    def close_h5_file(self):
        if hasattr(self, "h5_file") and self.h5_file.id is not None:
            self.h5_file.close()
