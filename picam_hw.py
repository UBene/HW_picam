from ScopeFoundry import HardwareComponent
try:
    from .picam import PiCAM  # , ROI_tuple
except Exception as err:
    print("Could not load modules needed for PICAM CCD:", err)

from . import picam_ctypes
from .picam_ctypes import PicamParameter


class PicamHW(HardwareComponent):

    name = "picam"

    def setup(self):
        # Create logged quantities
        self.settings.New('ccd_status', dtype=str, fmt="%s", ro=True)
        self.settings.New('roi_x', dtype=int, initial=0, si=False)
        self.settings.New('roi_w', dtype=int, initial=1340, si=False)
        self.settings.New('roi_x_bin', dtype=int, initial=1, si=False)
        self.settings.New('roi_y', dtype=int, initial=0, si=False)
        self.settings.New('roi_h', dtype=int, initial=100, si=False)
        self.settings.New('roi_y_bin', dtype=int, initial=1, si=False)

        # Auto-generate settings from PicamParameters
        for name, param in PicamParameter.items():
            self.settings['debug_mode']: self.log.info(
                'params: {} {}'.format(name, param))
            dtype_translate = dict(FloatingPoint=float,
                                   Boolean=bool, Integer=int)
            if param.param_type in dtype_translate:
                self.add_logged_quantity(
                    name=param.short_name, dtype=dtype_translate[param.param_type])

            elif param.param_type == 'Enumeration':
                enum_name = "Picam{}Enum".format(param.short_name)
                if hasattr(picam_ctypes, enum_name):
                    enum_obj = getattr(picam_ctypes, enum_name)
                    choice_names = enum_obj.bysname.keys()
                    self.add_logged_quantity(
                        name=param.short_name, dtype=str, choices=choice_names)

        # Customize auto-generated parameters
        self.settings.ExposureTime.change_unit('ms')
        self.settings.AdcSpeed.change_unit('MHz')

        # operations
        self.add_operation('commit_parameters', self.commit_parameters)

    def connect(self):
        if self.settings['debug_mode']:
            self.log.info("Connecting to PICAM")

        self.cam = PiCAM()

        supported_pnames = self.cam.get_param_names()

        for pname in supported_pnames:
            if pname in self.settings.as_dict():
                if self.settings['debug_mode']:
                    self.log.debug("connecting {}".format(pname))
                lq = self.settings.as_dict()[pname]
                if self.settings['debug_mode']:
                    self.log.debug("lq.name {}".format(lq.name))
                lq.hardware_read_func = lambda pname = pname: self.cam.read_param(
                    pname)
                if self.settings['debug_mode']:
                    self.log.debug("lq.read_from_hardware() {}".format(
                        lq.read_from_hardware()))
                rw = self.cam.get_param_readwrite(pname)
                if self.settings['debug_mode']:
                    self.log.debug("picam param rw {} {}".format(lq.name, rw))
                if rw in ['ReadWriteTrivial', 'ReadWrite']:
                    lq.hardware_set_func = lambda x, pname = pname: self.cam.write_param(
                        pname, x)
                elif rw == 'ReadOnly':
                    lq.change_readonly(True)
                else:
                    raise ValueError("picam param rw not understood", rw)

        for lqname in ['roi_x', 'roi_w', 'roi_x_bin', 'roi_y', 'roi_h', 'roi_y_bin']:
            self.settings.get_lq(lqname).updated_value.connect(self.write_roi)

        self.write_roi()
        self.cam.read_rois()
        self.commit_parameters()

    def write_roi(self, a=None):
        self.debug_mode: self.log.debug('write_roi')
        S = self.settings
        self.cam.write_single_roi(x=S['roi_x'], width=S['roi_w'], x_binning=S['roi_x_bin'],
                                  y=S['roi_y'], height=S['roi_h'], y_binning=S['roi_y_bin'])

    def disconnect(self):

        self.settings.disconnect_all_from_hardware()

        if hasattr(self, 'cam'):
            self.cam.close()
            del self.cam

    def commit_parameters(self):
        self.cam.commit_parameters()
