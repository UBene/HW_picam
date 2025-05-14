from ScopeFoundry import HardwareComponent


from . import picam_ctypes
from .picam_ctypes import PicamParameter


class PicamHW(HardwareComponent):

    name = "picam"

    def setup(self):
        s = self.settings
        self.m = []
        s.New("ccd_status", str, fmt="%s", ro=True)
        s.New(
            "target_serial_number",
            str,
            initial="OpenFirst",
            description=f"if only one camera is connect set <i>OpenFirst</i>. hit 'print available cameras' to see serial numbers",
        )

        s.New("serial_number", str, initial="", ro=True)
        s.New("sensor_name", str, initial="", ro=True)
        s.New("roi_x", int, initial=0)
        s.New("roi_w", int, initial=1600)
        s.New("roi_x_bin", int, initial=1, vmin=1)
        s.New("roi_y", int, initial=0)
        s.New("roi_h", int, initial=1)
        s.New("roi_y_bin", int, initial=1, vmin=1)

        # Auto-generate settings from PicamParameters
        dtype_translate = dict(
            FloatingPoint=float,
            Boolean=bool,
            Integer=int,
            LargeInteger=int,
        )

        for name, param in PicamParameter.items():
            self.log.info("params: {} {}".format(name, param))
            if param.param_type in dtype_translate:
                s.New(param.short_name, dtype_translate[param.param_type])
            elif param.param_type == "Enumeration":
                enum_name = "Picam{}Enum".format(param.short_name)
                if hasattr(picam_ctypes, enum_name):
                    enum_obj = getattr(picam_ctypes, enum_name)
                    choice_names = enum_obj.bysname.keys()
                    s.New(param.short_name, str, choices=choice_names)

        # Customize auto-generated parameters
        s.ExposureTime.change_unit("ms")
        s.AdcSpeed.change_unit("MHz")

        # operations
        self.add_operation("commit_parameters", self.commit_parameters)
        self.add_operation("print available cameras", self.print_available_cameras)

    def connect(self):
        s = self.settings
        if s["debug_mode"]:
            self.log.info("Connecting to PICAM")

        from .picam import PiCAM

        self.cam = PiCAM(s["debug_mode"], s["target_serial_number"])

        supported_pnames = self.cam.get_param_names()

        lq_dict = self.settings.as_dict()
        for pname in supported_pnames:
            if pname in self.settings.as_dict():
                self.log.debug("connecting {}".format(pname))
                lq = lq_dict[pname]
                self.log.debug("lq.name {}".format(lq.name))
                lq.hardware_read_func = lambda pname=pname: self.cam.read_param(pname)
                self.log.debug(
                    "lq.read_from_hardware() {}".format(lq.read_from_hardware())
                )
                rw = self.cam.get_param_readwrite(pname)
                self.log.debug("picam param rw {} {}".format(lq.name, rw))
                if rw in ["ReadWriteTrivial", "ReadWrite"]:
                    lq.hardware_set_func = lambda x, pname=pname: self.cam.write_param(
                        pname, x
                    )
                elif rw == "ReadOnly":
                    lq.change_readonly(True)
                else:
                    raise ValueError("picam param rw not understood", rw)

        for lqname in ["roi_x", "roi_w", "roi_x_bin", "roi_y", "roi_h", "roi_y_bin"]:
            self.settings.get_lq(lqname).updated_value.connect(self.write_roi)

        self.read_from_hardware()
        s.serial_number.connect_to_hardware(self.cam.serial_number)
        s.sensor_name.connect_to_hardware(self.cam.sensor_name)
        if self.cam.supports_rois:
            s.roi_w.change_min_max(1, s["SensorActiveWidth"])
            s.roi_x_bin.change_min_max(1, s["SensorActiveWidth"])
            s.roi_h.change_min_max(1, s["SensorActiveHeight"])
            s.roi_y_bin.change_min_max(1, s["SensorActiveHeight"])
            self.write_roi()
            self.cam.read_rois()
        self.commit_parameters()

    def write_roi(self, a=None):
        if not self.cam.supports_rois:
            return
        s = self.settings
        self.cam.write_single_roi(
            x=s["roi_x"],
            width=s["roi_w"],
            x_binning=s["roi_x_bin"],
            y=s["roi_y"],
            height=s["roi_h"],
            y_binning=s["roi_y_bin"],
        )

        s["ActiveWidth"] = s["roi_w"]
        s["ActiveHeight"] = s["roi_h"]

    def get_shape(self):
        s = self.settings
        return (s["roi_w"] // s["roi_x_bin"], s["roi_h"] // s["roi_y_bin"])

    def disconnect(self):
        self.settings.disconnect_all_from_hardware()
        if hasattr(self, "cam"):
            self.cam.close()
            del self.cam

    def commit_parameters(self):
        self.cam.commit_parameters()

    def print_available_cameras(self):
        from .picam_cam_manager import manager

        manager.print_available_cameras()
