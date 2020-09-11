from ScopeFoundry import Measurement, h5_io
import pyqtgraph as pg
import numpy as np
from qtpy import QtWidgets
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import time

class PicamReadoutMeasure(Measurement):

    name = "picam_readout"
    
    def setup(self):

        #local logged quantities
        self.save_h5 = self.settings.New('save_h5', dtype = bool, initial=False)
        self.continuous = self.settings.New('continuous', dtype=bool, initial=True)
        self.wl_calib = self.settings.New('wl_calib', dtype=str, initial='pixels', 
                          choices=('pixels', 'raw_pixels', 'acton_spectrometer', 'wave_numbers', 'raman_shifts'))
        self.laser_wl = self.settings.New('laser_wl', initial = 532.0, vmin=1e-15)
        
        

        
        #connect events
        
        
        self.display_update_period = 0.050 #seconds
        self.spec_hw  = self.app.hardware['picam']
        
        


    def run(self):

        cam = self.spec_hw.cam

        print("rois|-->", cam.read_rois())

        cam.commit_parameters()
        
        while not self.interrupt_measurement_called:
            self.t0 = time.time()
            
            dat = cam.acquire(readout_count=1, readout_timeout=-1)
            
            self.roi_data = cam.reshape_frame_data(dat)
            #print "roi_data shapes", [d.shape for d in self.roi_data]            
            self.spec = spec  = np.average(self.roi_data[0], axis=0)
            
            px_index = np.arange(self.spec.shape[-1])
            self.hbin = self.spec_hw.settings['roi_x_bin']

            if 'acton_spectrometer' in self.app.hardware:
                self.wls = self.app.hardware['acton_spectrometer'].get_wl_calibration(px_index, self.hbin)
            else:
                self.wls =  self.hbin*px_index + 0.5*(self.hbin-1)
            self.pixels = self.hbin*px_index + 0.5*(self.hbin-1)
            self.raw_pixels = px_index
            self.wave_numbers = 1.0e7/self.wls
            self.raman_shifts = 1.0e7/self.laser_wl.val - 1.0e7/self.wls
            
            
            self.wls_mean = self.wls.mean()

            if not self.continuous.val:
                break
            

        if self.settings['save_h5']:
            self.h5_file = h5_io.h5_base_file(self.app, measurement=self )
            self.h5_file.attrs['time_id'] = self.t0
            H = self.h5_meas_group  =  h5_io.h5_create_measurement_group(self, self.h5_file)
              
            H['spectrum'] = spec
            H['wavelength'] = self.wls
            H['wave_numbers'] = self.wave_numbers
            H['raman_shifts'] = self.raman_shifts
            
            print('saved file')
            
            self.h5_file.close()
            

    def setup_figure(self):


        self.ui = load_qt_ui_file(sibling_path(__file__, 'picam_readout.ui'))
        
        self.spec_hw.settings.ExposureTime.connect_to_widget(self.ui.int_time_doubleSpinBox) 
        self.spec_hw.settings.SensorTemperatureReading.connect_to_widget(self.ui.temp_doubleSpinBox) 

        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
        self.ui.commit_pushButton.clicked.connect(self.spec_hw.commit_parameters)

        self.save_h5.connect_to_widget(self.ui.save_h5_checkBox)
        self.continuous.connect_to_widget(self.ui.continuous_checkBox)
        self.wl_calib.connect_to_widget(self.ui.wl_calib_comboBox)


        if hasattr(self, 'graph_layout'):
            self.graph_layout.deleteLater() # see http://stackoverflow.com/questions/9899409/pyside-removing-a-widget-from-a-layout
            del self.graph_layout
        self.graph_layout = pg.GraphicsLayoutWidget(border=(0,0,0))
        self.ui.plot_groupBox.layout().addWidget(self.graph_layout)
        
        self.spec_plot = self.graph_layout.addPlot()
        self.spec_plot_line = self.spec_plot.plot([1,3,2,4,3,5])
        self.spec_plot.enableAutoRange()
                
        self.graph_layout.nextRow()

        self.img_plot = self.graph_layout.addPlot()
        self.img_item = pg.ImageItem()
        self.img_plot.addItem(self.img_item)
        self.img_plot.showGrid(x=True, y=True)
        self.img_plot.setAspectLocked(lock=True, ratio=1)

        self.hist_lut = pg.HistogramLUTItem()
        self.hist_lut.autoHistogramRange()
        self.hist_lut.setImageItem(self.img_item)
        self.graph_layout.addItem(self.hist_lut)

    def update_display(self):
        self.img_item.setImage(self.roi_data[0].T.astype(float), autoLevels=False)
        self.hist_lut.imageChanged(autoLevel=True, autoRange=True)
        
        wl_calib = self.settings['wl_calib']
        if wl_calib=='acton_spectrometer':
            x = self.wls
        elif wl_calib=='pixels':
            x = self.pixels
        elif wl_calib=='raw_pixels':
            x = self.raw_pixels
        elif wl_calib=='wave_numbers':
            x = self.wave_numbers
        elif wl_calib=='raman_shifts':
            x = self.raman_shifts            
            
        spec = np.average(self.roi_data[0], axis=0)
        self.spec_plot_line.setData(x,spec)