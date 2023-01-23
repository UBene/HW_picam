from ScopeFoundry import HardwareComponent

from . import picam_ctypes
from .picam_ctypes import PicamParameter


class PicamHW(HardwareComponent):

    name = "picam"

    def setup(self):
        # Create settings
        S = self.settings
        S.New("serial_number", str, initial="", ro=False,
              description="""before connection: sn of desired camera, 
                after connection: effective serial number 
                (falls back to first camera if desired device was not found)""")

        S.New("ccd_status", dtype=str, fmt="%s", ro=True)
        S.New("roi_x", dtype=int, initial=0, si=False)
        S.New("roi_w", dtype=int, initial=1340, si=False)
        S.New("roi_x_bin", dtype=int, initial=1, si=False)
        S.New("roi_y", dtype=int, initial=0, si=False)
        S.New("roi_h", dtype=int, initial=100, si=False)
        S.New("roi_y_bin", dtype=int, initial=1, si=False)

        # Auto-generate settings from PicamParameters
        for name, param in PicamParameter.items():
            S["debug_mode"]: self.log.info(
                "params: {} {}".format(name, param)
            )
            dtype_translate = dict(FloatingPoint=float,
                                   Boolean=bool, Integer=int)
            if param.param_type in dtype_translate:
                self.settings.New(
                    name=param.short_name, dtype=dtype_translate[param.param_type]
                )

            elif param.param_type == "Enumeration":
                enum_name = "Picam{}Enum".format(param.short_name)
                if hasattr(picam_ctypes, enum_name):
                    enum_obj = getattr(picam_ctypes, enum_name)
                    choice_names = enum_obj.bysname.keys()
                    self.settings.New(
                        name=param.short_name, dtype=str, choices=choice_names
                    )

        # Customize auto-generated parameters
        S.ExposureTime.change_unit("ms")
        S.AdcSpeed.change_unit("MHz")
        S.New("dll_path", str,
              initial=r"C:\Program Files\Princeton Instruments\Picam\Runtime\Picam.dll")
        S.New("sensor_name", str, initial="", ro=True)
        # operations
        self.add_operation("commit_parameters", self.commit_parameters)

    def connect(self):
        from .picam import PiCAM

        S = self.settings

        if S["debug_mode"]:
            self.log.info("Connecting to PICAM")

        self.cam = PiCAM(debug=S["debug_mode"],
                         picam_dll_fname=S["dll_path"],
                         desired_sn=S["serial_number"])

        supported_pnames = self.cam.get_param_names()

        for pname in supported_pnames:
            if pname in S.as_dict():
                if S["debug_mode"]:
                    self.log.debug("connecting {}".format(pname))
                lq = S.as_dict()[pname]
                if S["debug_mode"]:
                    self.log.debug("lq.name {}".format(lq.name))
                lq.hardware_read_func = lambda pname = pname: self.cam.read_param(
                    pname)
                if S["debug_mode"]:
                    self.log.debug(
                        "lq.read_from_hardware() {}".format(lq.read_from_hardware())
                    )
                rw = self.cam.get_param_readwrite(pname)
                if S["debug_mode"]:
                    self.log.debug("picam param rw {} {}".format(lq.name, rw))
                if rw in ["ReadWriteTrivial", "ReadWrite"]:
                    lq.hardware_set_func = lambda x, pname = pname: self.cam.write_param(
                        pname, x
                    )
                elif rw == "ReadOnly":
                    lq.change_readonly(True)
                else:
                    raise ValueError("picam param rw not understood", rw)

        for lqname in ["roi_x", "roi_w", "roi_x_bin", "roi_y", "roi_h", "roi_y_bin"]:
            S.get_lq(lqname).updated_value.connect(self.write_roi)

        self.write_roi()
        self.cam.read_rois()
        self.commit_parameters()
        S['sensor_name'] = self.cam.sensor_name
        S['serial_number'] = self.cam.serial_number

    def write_roi(self, a=None):
        S = self.settings
        if S['debug_mode']:
            self.log.debug("write_roi")
        self.cam.write_single_roi(
            x=S["roi_x"],
            width=S["roi_w"],
            x_binning=S["roi_x_bin"],
            y=S["roi_y"],
            height=S["roi_h"],
            y_binning=S["roi_y_bin"],
        )

    def disconnect(self):

        self.settings.disconnect_all_from_hardware()

        if hasattr(self, "cam"):
            self.cam.close()
            del self.cam

    def commit_parameters(self):
        self.cam.commit_parameters()
