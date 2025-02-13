import collections
import ctypes
import time
from ctypes import byref

import numpy as np

from . import picam_ctypes
from .picam_cam_manager import OPEN_FIRST, manager

ROI_tuple = collections.namedtuple(
    'ROI_tuple', "x width x_binning y height y_binning")

PI = manager.get_dll()


class PiCAM(object):

    def __init__(self, debug=False, target_sn=OPEN_FIRST):
        self.debug = debug
        self.camera_handle, self.camera_id = manager.open_camera(
            target_sn)
        self.supports_rois = self.can_set_first_px_as_roi()

    def sensor_name(self):
        return self.camera_id.sensor_name.decode()

    def serial_number(self):
        return self.camera_id.serial_number.decode()

    def close(self):
        manager.close_camera(self.camera_handle)

    def read_param(self, pname):
        if self.debug:
            print(("read_param", pname))

        param = picam_ctypes.PicamParameter["PicamParameter_" + pname]

        ptype = param.param_type
        if ptype in ['Integer', 'Boolean', 'i', 'I', int]:
            val = picam_ctypes.piint()
            self._err(PI.Picam_GetParameterIntegerValue(
                self.camera_handle, param.enum, byref(val)))
        elif ptype in ['LargeInteger']:
            val = picam_ctypes.pi64s()
            self._err(PI.Picam_GetParameterLargeIntegerValue(
                self.camera_handle, param.enum, byref(val)))
        elif ptype in ['FloatingPoint', 'f', 'F', float]:
            val = ctypes.c_double()
            self._err(PI.Picam_GetParameterFloatingPointValue(
                self.camera_handle, param.enum, byref(val)))
        elif ptype in ['Enumeration']:
            val = ctypes.c_int()
            self._err(PI.Picam_GetParameterIntegerValue(
                self.camera_handle, param.enum, byref(val)))
            enum_name = "Picam{}Enum".format(pname)
            if hasattr(picam_ctypes, enum_name):
                enum_obj = getattr(picam_ctypes, enum_name)
                enum_name = enum_obj.bynums[val.value]
                # print "PI_read_param", pname, ptype, val, repr(val.value), enum_name
                # return val.value, enum_name
                return enum_name

        elif ptype in ['Rois']:
            rois_p = ctypes.POINTER(picam_ctypes.PicamRois)()
            self._err(PI.Picam_GetParameterRoisValue(
                self.camera_handle, param.enum, byref(rois_p)))
            rois = rois_p.contents
            # print "roi_count", rois.roi_count
            # print "roi_array",rois.roi_array[0]

            # rois_array = np.fromiter(rois.roi_array, dtype=picam_ctypes.PicamRoi, count=rois.roi_count)
            # roi_dict_array = [ ROI_tuple(*roi) for roi in rois_array ]

            # Populate the tuple using a loop instead of direct assignment
            roi_dict_array = list(np.empty(rois.roi_count))
            for i in range(rois.roi_count):
                itup = ROI_tuple(rois.roi_array[i].x,
                                 rois.roi_array[i].width,
                                 rois.roi_array[i].x_binning,
                                 rois.roi_array[i].y,
                                 rois.roi_array[i].height,
                                 rois.roi_array[i].y_binning,
                                 )
                roi_dict_array[i] = itup

            self._err(PI.Picam_DestroyRois(rois_p))
            return roi_dict_array
        else:
            raise ValueError(
                "PI_read_param ptype not understood: {}".format(repr(ptype)))

        # print "read_param", pname, ptype, val, repr(val.value)
        if ptype == 'Boolean':
            return bool(val.value)
        return val.value

    def write_param(self, pname, newval):
        param = picam_ctypes.PicamParameter["PicamParameter_" + pname]
        ptype = param.param_type

        if self.debug:
            print('write_param', pname, newval, ptype, param)

        # TODO check for read only
        
        

        if ptype in ['Integer', 'i', 'I', int]:
            settable = ctypes.c_int()
            self._err(PI.Picam_CanSetParameterIntegerValue(
                self.camera_handle, param.enum, newval, byref(settable)))
            if not settable.value:
                raise ValueError(
                    "PICAM write_param failed: {} --> {} not allowed".format(pname, newval))
            self._err(PI.Picam_SetParameterIntegerValue(
                self.camera_handle, param.enum, newval))
        elif ptype in ['FloatingPoint', 'f', 'F', float]:
            self._err(PI.Picam_SetParameterFloatingPointValue(
                self.camera_handle, param.enum, picam_ctypes.piflt(newval)))
        elif ptype in ['Enumeration']:
            enum_name = "Picam{}Enum".format(param.short_name)
            if not hasattr(picam_ctypes, enum_name):
                raise ValueError(
                    "PICAM write_param failed: {} --> {} not allowed".format(pname, newval))
            enum_obj = getattr(picam_ctypes, enum_name)
            newval_id = enum_obj.bysname[newval]
            if self.debug:
                print('enum', newval, newval_id)
            self._err(PI.Picam_SetParameterIntegerValue(
                self.camera_handle, param.enum, newval_id))

        else:
            raise ValueError(
                "PI write_param ptype not understood: {}".format(repr(ptype)))

    def get_param_readwrite(self, pname):
        """
        PICAM_API Picam_GetParameterValueAccess(
        PicamHandle       camera,
        PicamParameter    parameter,
        PicamValueAccess* access );

        ##
        PicamValueAccess_ReadOnly         = 1,
        PicamValueAccess_ReadWriteTrivial = 3,
        PicamValueAccess_ReadWrite        = 2     
        """
        param = picam_ctypes.PicamParameter["PicamParameter_" + pname]
        access = ctypes.c_int(0)

        self._err(PI.Picam_GetParameterValueAccess(
            self.camera_handle, param.enum, byref(access)))
        if self.debug:
            print("get_param_readwrite", pname, access, access.value)
        return picam_ctypes.PicamValueAccess[access.value].split('_')[-1]

    def commit_parameters(self):

        failed_param_array = ctypes.POINTER(ctypes.c_int)()
        failed_pcount = picam_ctypes.piint()

        self._err(PI.Picam_CommitParameters(self.camera_handle,
                  byref(failed_param_array), byref(failed_pcount)))
        a = np.fromiter(failed_param_array, dtype=int,
                        count=failed_pcount.value)
        self._err(PI.Picam_DestroyParameters(failed_param_array))

        return [picam_ctypes.PicamParameterEnum.bynums[x] for x in a]

    def get_param_names(self):

        param_array = ctypes.c_void_p()
        pcount = picam_ctypes.piint()

        self._err(PI.Picam_GetParameters(
            self.camera_handle, byref(param_array), byref(pcount)))
        data_p = ctypes.cast(param_array, ctypes.POINTER(ctypes.c_int))
        a = np.fromiter(data_p, dtype=int, count=pcount.value)
        self._err(PI.Picam_DestroyParameters(param_array))
        param_list = []

        # Skip invalid parameters
        for x in a:
            if x in picam_ctypes.PicamParameterEnum.bynums:
                # print(picam_ctypes.PicamParameterEnum.bynums[x])
                param_list.append(picam_ctypes.PicamParameterEnum.bynums[x])
            else:
                print(picam_ctypes.PicamParameterEnum.bynums[x])

        return param_list

    def read_rois(self):
        if not self.supports_rois:
            return
        self.roi_array = self.read_param('Rois')
        return self.roi_array

    def can_set_first_px_as_roi(self):
        rois_list = [ROI_tuple(0, 1, 1, 0, 1, 1)]
        param = picam_ctypes.PicamParameter["PicamParameter_Rois"]
        rois = picam_ctypes.PicamRois()
        roi_np_array = np.empty(
            len(rois_list), dtype=type(picam_ctypes.PicamRoi))
        roi_array_type = picam_ctypes.PicamRoi*len(roi_np_array)
        roi_array = roi_array_type(*rois_list)
        rois.roi_array = roi_array
        rois.roi_count = picam_ctypes.piint(len(roi_np_array))
        can_set = ctypes.c_bool()
        try:
            self._err(PI.Picam_CanSetParameterRoisValue(
                self.camera_handle, param.enum, rois, byref(can_set)))
            return can_set.value
        except IOError:
            return False

    def write_rois(self, rois_list):
        if not self.supports_rois:
            print(
                'setting rois not supported: If you believe that your camera does support check initializer')
            return

        param = picam_ctypes.PicamParameter["PicamParameter_Rois"]

        roi_np_array = np.empty(
            len(rois_list), dtype=type(picam_ctypes.PicamRoi))

        roi_array_type = picam_ctypes.PicamRoi*len(roi_np_array)
        roi_array = roi_array_type(*rois_list)

        rois = picam_ctypes.PicamRois()
        rois.roi_array = roi_array
        rois.roi_count = picam_ctypes.piint(len(roi_np_array))

        self._err(PI.Picam_SetParameterRoisValue(
            self.camera_handle, param.enum, rois))
        self.read_rois()

    def write_single_roi(self, x, width, x_binning, y, height, y_binning):
        return self.write_rois([ROI_tuple(x, width, x_binning, y, height, y_binning)])

    def acquire(self, readout_count=1, readout_timeout=-1):
        readout_count = picam_ctypes.pi64s(readout_count)
        readout_time_out = picam_ctypes.piint(readout_timeout)
        available = picam_ctypes.PicamAvailableData()
        errors = ctypes.c_int()

        # import time

        if self.debug:
            t0 = time.time()
        self._err(PI.Picam_Acquire(self.camera_handle, readout_count,
                  readout_time_out, byref(available), byref(errors)))
        if self.debug:
            print("Picam_Acquire time", time.time() - t0)
            print("available.initial_readout: ", available.initial_readout)
            print("available.readout_count: ", available.readout_count)
            print("Initial readout type is", type(available.initial_readout))

        # t0 = time.time()
        data_p = ctypes.cast(available.initial_readout, ctypes.POINTER(
            picam_ctypes.pi16s*(self.read_param('ReadoutStride')//2)))
        # data = np.fromiter(data_p, dtype=np.int16, count=readout_count.value*self.read_param('ReadoutStride'))
        data = np.frombuffer(data_p.contents, dtype=np.uint16)
        # print("data conversion time", time.time() - t0)

        return data

        '''
        def get_data(self):
        """ Routine to access initial data.
        Returns numpy array with shape (400,1340) """

        """ Create an array type to hold 1340x400 16bit integers """
        DataArrayType = pi16u*self.myroi.width*self.myroi.height

        """ Create pointer type for the above array type """
        DataArrayPointerType = ctypes.POINTER(pi16u*self.myroi.width*self.myroi.height)

        """ Create an instance of the pointer type, and point it to initial readout contents (memory address?) """
        DataPointer = ctypes.cast(self.available.initial_readout,DataArrayPointerType)


        """ Create a separate array with readout contents """
        # TODO, check this stuff for slowdowns
        rawdata = DataPointer.contents
        numpydata = numpy.frombuffer(rawdata, dtype='uint16')
        data = numpy.reshape(numpydata,(self.myroi.height,self.myroi.width))  # TODO: get dimensions officially,
        # note, the readoutstride is the number of bytes in the array, not the number of elements
        # will need to be smarter about the array size, but for now it works.
        return data
        '''

    def reshape_frame_data(self, dat):
        if not self.supports_rois:
            return [dat.reshape(1, -1)]

        roi_array = self.roi_array
        roi_datasets = []
        offset = 0
        for roi in roi_array:
            Nx = roi.width//roi.x_binning
            Ny = roi.height//roi.y_binning
            roi_size = Nx*Ny
            dset = dat[offset:offset+roi_size].reshape(Ny, Nx)
            roi_datasets.append(dset)
            offset += roi_size
        return roi_datasets

    def _err(self, err):
        if err == 0:
            return err
        else:
            err_str = picam_ctypes.PicamErrorEnum.bynum[err]
            raise IOError(err_str)

    def read_roi_data(self, readout_count=1, readout_timeout=-1):
        dat = self.acquire(readout_count=readout_count,
                           readout_timeout=readout_timeout)
        return np.array(self.reshape_frame_data(dat))


if __name__ == '__main__':

    cam = PiCAM(debug=True)

    pnames = cam.get_param_names()

    for pname in pnames:
        try:
            val = cam.read_param(pname)
            print((pname, "\t\t", repr(val)))
        except ValueError as err:
            print(("skip", pname, err))

    readoutstride = cam.read_param("ReadoutStride")

    cam.write_param('ExposureTime', 100)
    print("exposuretime", cam.read_param('ExposureTime'))

    print("commit", cam.commit_parameters())

    cam.read_param('PixelHeight')
    cam.read_param('SensorTemperatureReading')
    cam.read_param('SensorTemperatureStatus')
    cam.read_param('ExposureTime')  # milliseconds
    cam.write_param('ExposureTime', 100.)

    # cam.write_rois([dict(x=0, width=100,x_binning=1, y=0, height=20, y_binning=1)])
    cam.write_rois(
        [ROI_tuple(x=0, width=1340, x_binning=1, y=0, height=100, y_binning=1)])
    print("rois|-->", cam.read_rois())

    print("roi0:", repr(cam.roi_array[0]))

    cam.commit_parameters()

    for pname in ["ReadoutStride", "FrameStride"]:
        print(":::", pname, cam.read_param(pname))

    ex_time = 0.010
    t0 = time.time()
    dat = cam.acquire(ex_time)
    t1 = time.time()
    print("data acquisition of exp_time of {} sec took {} sec".format(ex_time, t1-t0))
    print("dat.shape", dat.shape)

    roi_data = cam.reshape_frame_data(dat)
    print("roi_data shapes", [d.shape for d in roi_data])

    import matplotlib.pylab as plt

    # plt.plot(roi_data[0].squeeze())
    # plt.ylim(np.percentile(roi_data[0], 1), np.percentile(roi_data[0],80))
    plt.imshow(roi_data[0], interpolation='none', vmin=np.percentile(
        dat, 1), vmax=np.percentile(dat, 99))
    plt.show()
    cam.close()
