from ScopeFoundryHW.picam.picam import PiCAM, ROI_tuple
import numpy  as np

cam = PiCAM(debug=True)
    
pnames = cam.get_param_names()

for pname in pnames:
    try:
        val = cam.read_param(pname)
        print(( pname,"\t\t", repr(val)))
    except ValueError as err:
        print(( "skip", pname, err)) 

readoutstride = cam.read_param("ReadoutStride")

cam.write_param('ExposureTime', 100)
print("exposuretime", cam.read_param('ExposureTime'))


print("commit", cam.commit_parameters())
        
cam.read_param('PixelHeight')
cam.read_param('SensorTemperatureReading')
cam.read_param('SensorTemperatureStatus')
cam.read_param('ExposureTime') # milliseconds

print("AdcQuality", cam.read_param("AdcQuality"))
cam.write_param("AdcQuality", 'HighCapacity')

print("AdcSpeed", cam.read_param("AdcSpeed"))
print("AdcSpeed", cam.write_param("AdcSpeed", 2.0))
print("AdcSpeed", cam.read_param("AdcSpeed"))
print("CleanCycleCount", cam.read_param("CleanCycleCount"))
print("CleanCycleCount", cam.write_param("CleanCycleCount", 0))
print("CleanCycleCount", cam.read_param("CleanCycleCount"))
#print("CleanBeforeExposure", cam.read_param("CleanBeforeExposure"))
#VerticalShiftRate


ex_time = 1.
cam.write_param('ExposureTime', ex_time)

#cam.write_rois([dict(x=0, width=100,x_binning=1, y=0, height=20, y_binning=1)])
cam.write_rois([ROI_tuple(x=0, width=1340,x_binning=1, y=0, height=100, y_binning=100)])
print("rois|-->", cam.read_rois())

print("roi0:", repr(cam.roi_array[0]))

cam.commit_parameters()

for pname in ["ReadoutStride", "FrameStride"]:
    print(":::", pname, cam.read_param(pname))

import time
t0 = time.time()
dat = cam.acquire(readout_count=1, readout_timeout=1000)
t1 = time.time()
print("data acquisition  frame with  exp_time of {} ms took {} sec".format(ex_time, t1-t0))
print("dat.shape", dat.shape)

roi_data = cam.reshape_frame_data(dat)
print("roi_data shapes", [d.shape for d in roi_data])

import matplotlib.pylab as plt
#plt.plot(roi_data[0].squeeze())
#plt.ylim(np.percentile(roi_data[0], 1), np.percentile(roi_data[0],80))
plt.imshow(roi_data[0], interpolation='none', vmin=np.percentile(dat, 1), vmax=np.percentile(dat,99))
plt.show()
cam.close()
