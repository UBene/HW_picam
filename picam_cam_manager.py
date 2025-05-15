import ctypes
from typing import Tuple

from .picam_ctypes import PicamCameraID, PicamHandle, piint

DLL_PATH = r"C:\Program Files\Princeton Instruments\PICam\Runtime\Picam.dll"
OPEN_FIRST = "OpenFirst"


def print_struct_fields(s):
    for field in s._fields_:
        print("\t", field[0], getattr(s, field[0]))


def _read_available_camera_ids(dll, debug=False):
    ptr = ctypes.c_void_p()
    id_count = piint()
    dll.Picam_GetAvailableCameraIDs(ctypes.byref(ptr), ctypes.byref(id_count))
    if debug:
        print("read_available_cameras counts:", id_count.value)
    return ctypes.cast(ptr, ctypes.POINTER(PicamCameraID * id_count.value))[0]


def open_camera_by_sn(dll, sn, debug=False) -> Tuple[PicamHandle, PicamCameraID]:
    camera_ids = _read_available_camera_ids(dll, debug)
    for camera_id in camera_ids:
        if debug:
            print(camera_id.serial_number.decode(), sn)
        if camera_id.serial_number.decode() == sn:
            camera_handle = PicamHandle()
            dll.Picam_OpenCamera(ctypes.byref(camera_id), ctypes.byref(camera_handle))
            return camera_handle, camera_id
    raise IOError(f"camera with {sn=} not found")


def open_first_camera(dll, debug=False) -> Tuple[PicamHandle, PicamCameraID]:
    camera_handle = PicamHandle()
    dll.Picam_OpenFirstCamera(ctypes.byref(camera_handle))
    camera_id = PicamCameraID()
    dll.Picam_GetCameraID(camera_handle, ctypes.byref(camera_id))
    return camera_handle, camera_id


class PicamCamManager:

    def __init__(self, debug=False):
        self.debug = debug

    def get_dll(self):
        if not hasattr(self, "dll"):
            self.load_library()
            self.init()
        return self.dll

    def open_camera(
        self, sn: str = OPEN_FIRST, debug=None
    ) -> Tuple[PicamHandle, PicamCameraID]:
        if debug is not None:
            self.debug = debug

        if not self.is_inited():
            self.init()

        if sn == OPEN_FIRST:
            return open_first_camera(self.dll, self.debug)
        else:
            return open_camera_by_sn(self.dll, sn, self.debug)

    def close_camera(self, camera_handle: PicamHandle) -> None:
        if self.is_inited():
            self.dll.Picam_CloseCamera(camera_handle)

    def load_library(self):
        self.dll = ctypes.cdll.LoadLibrary(DLL_PATH)

    def init(self):
        self.dll.Picam_InitializeLibrary()

    def un_init(self):
        self.dll.Picam_UninitializeLibrary()

    def is_inited(self):
        inited = ctypes.c_bool()
        self.dll.Picam_IsLibraryInitialized(ctypes.byref(inited))
        return inited.value

    def re_init(self):
        if self.is_inited():
            self.un_init()
        self.init()

    def print_available_cameras(self):
        self.dll = self.get_dll()
        id_array = _read_available_camera_ids(self.dll, self.debug)
        for ii, cam_id in enumerate(id_array):
            print(ii + 1)
            print_struct_fields(cam_id)

    def get_available_cameras(self):
        id_array = _read_available_camera_ids(self.dll, self.debug)
        return [{i.serial_number.decode(): i.sensor_name.decode()} for i in id_array]


manager = PicamCamManager(True)
