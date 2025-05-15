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
        s.New("roi_x", int, initial=0, description=ROI_DESCRIPTION)
        s.New("roi_w", int, initial=1600, description=ROI_DESCRIPTION)
        s.New("roi_x_bin", int, initial=1, vmin=1, description=ROI_DESCRIPTION)
        s.New("roi_y", int, initial=0, description=ROI_DESCRIPTION)
        s.New("roi_h", int, initial=1, description=ROI_DESCRIPTION)
        s.New("roi_y_bin", int, initial=1, vmin=1, description=ROI_DESCRIPTION)

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
        s.ExposureTime.spinbox_decimals = 3

        s.AdcSpeed.change_unit("MHz")
        s.get_lq("FrameRateCalculation").change_unit("Hz")
        s.get_lq("FrameRateCalculation").description = (
            "The maximum number of frames per second that camera can acquire is a function of roi, ExposureTime, VerticalShift ..."
        )
        s.get_lq("VerticalShiftRate").change_unit("us")
        s.get_lq("VerticalShiftRate").spinbox_decimals = 6
        s.get_lq("VerticalShiftRate").description = VERTICAL_SHIFT_DESCRIPTION
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
        self.commit_parameters()

    def write_roi(self, a=None):
        if not self.cam.supports_rois:
            return

        s = self.settings

        # confusing way to define active region??
        # first activate more than you need
        s["ActiveWidth"] = s["roi_w"] + s["roi_x"]
        s["ActiveHeight"] = s["roi_h"] + s["roi_y"]
        # second deactivate what you do not need.
        s["ActiveLeftMargin"] = s["roi_x"]
        s["ActiveBottomMargin"] = s["roi_y"]
        
        self.cam.write_single_roi(
            x=s["roi_x"],
            width=s["roi_w"],
            x_binning=s["roi_x_bin"],
            y=s["roi_y"],
            height=s["roi_h"],
            y_binning=s["roi_y_bin"],
        )



        

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


VERTICAL_SHIFT_DESCRIPTION = """Controls the rate to shift one row towards the serial register in a CCD in microseconds. 

The valid values depend on the model (or specific camera?):

<b>pixis:</b> 6.2, 9.2, 12.2, 15.2, 18.2, 21.2, 24.2, 27.2, 30.2 ,33.2, 36.2, 39.2, 42.2, 45.2, and 48.2 us

<b>pro_em:</b> 0.6, 2us ... ?

<b>pylon:</b> NA

<b>blaze:</b> ?
"""

ROI_DESCRIPTION = """Defines the Region of Interest, that is the section of the sensor and the Binning of the Image. In this Implementation the active area is reduced to minimize acquisition time."""
