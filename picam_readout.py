from ScopeFoundry import Measurement, h5_io
import pyqtgraph as pg
import numpy as np
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import time


class PicamReadoutMeasure(Measurement):
    
    name = "picam_readout"
    
    def setup(self):

        self.settings.New('save_h5', dtype=bool, initial=False)
        self.settings.New('continuous', dtype=bool, initial=True)
        self.settings.New('wl_calib', dtype=str, initial='pixels',
                          choices=('pixels',
                                   'raw_pixels',
                                   'spectrometer',
                                   'wave_numbers',
                                   'raman_shifts'))
        self.settings.New('laser_wl', initial=532.0, vmin=1e-15,
                          unit='nm',
                          description='used to calculate raman_shifts')
        self.settings.New('count_rate', float, unit='Hz')
        self.settings.New('spec_hw', str, initial='pi_spectrometer',
                          choices=('pi_spectrometer',
                                     'acton_spectrometer'))
        self.settings.New('flip_x', bool, initial=True)
        self.settings.New('flip_y', bool, initial=False)
        self.settings.New('background_subtract', bool, initial=False)
        
        self.display_update_period = 0.050  # seconds
        self.cam_hw = self.app.hardware['picam']
        self.wls = np.arange(512) + 1  # initialize dummy wls
        self.background = np.zeros_like(self.wls)
        self.spectrum = np.sin(self.wls)
        self.add_operation('update_background', self.update_background)
        self.data = {'spectrum':self.spectrum,
                     'wavelengths':self.wls,
                     'wave_numbers':1 / self.wls,
                     'raman_shifts':self.wls}
        
    def read_cam_data(self, readout_count=1):
        dat = self.cam_hw.cam.acquire(readout_count=readout_count, readout_timeout=-1)
        roi_data = np.array(self.cam_hw.cam.reshape_frame_data(dat))
        if self.settings['flip_x']:
            roi_data = np.flip(roi_data, axis=-1)
        if self.settings['flip_y']:
            roi_data = np.flip(roi_data, -2)
        return roi_data
    
    def read_spectrum_data(self, readout_count=1):
        roi_data = self.read_cam_data(readout_count=readout_count)
        return np.average(roi_data[0], axis=0)
        
    def update_background(self):
        print(self.name, 'start updating background',
              5 * self.cam_hw.settings['ExposureTime'] / 1000, 's')
        self.background = self.read_spectrum_data(readout_count=5)         
        self.settings['background_subtract'] = True
        print(self.name, 'background updated')
        
    def run(self):

        S = self.settings
        cam = self.cam_hw.cam

        # print("rois|-->", cam.read_rois())

        cam.commit_parameters()
        
        while not self.interrupt_measurement_called:
            self.t0 = time.time()
            
            self.acq_time = time.time() - self.t0
            
            self.roi_data = self.read_cam_data()
            self.spectrum = np.average(self.roi_data[0], axis=0)
            if S['background_subtract']:
                self.spectrum = self.spectrum - self.background
            
            px_index = np.arange(self.spectrum.shape[-1])
            self.hbin = self.cam_hw.settings['roi_x_bin']

            if 'acton_spectrometer' in self.app.hardware and S['spec_hw'] == 'acton_spectrometer':
                hw = self.app.hardware['acton_spectrometer']
                self.wls = hw.get_wl_calibration(px_index, self.hbin)
            elif 'pi_spectrometer' in self.app.hardware and S['spec_hw'] == 'pi_spectrometer':
                hw = self.app.hardware['pi_spectrometer']
                self.wls = hw.get_wl_calibration(px_index, self.hbin)
            else:
                self.wls = self.hbin * px_index + 0.5 * (self.hbin - 1)
            self.pixels = self.hbin * px_index + 0.5 * (self.hbin - 1)
            self.raw_pixels = px_index
            self.wave_numbers = 1.0e7 / self.wls
            self.raman_shifts = 1.0e7 / S['laser_wl'] - 1.0e7 / self.wls
            
            self.wls_mean = self.wls.mean()

            S['count_rate'] = self.spectrum.sum() / (self.cam_hw.settings['ExposureTime'] / 1000.0)

            if not S['continuous']:
                break
            
        self.data['spectrum'] = self.spectrum
        self.data['wavelengths'] = self.wls
        self.data['wave_numbers'] = self.wave_numbers
        self.data['raman_shifts'] = self.raman_shifts        

        if S['save_h5']:
            self.h5_file = h5_io.h5_base_file(self.app, measurement=self)
            self.h5_file.attrs['time_id'] = self.t0
            H = self.h5_meas_group = h5_io.h5_create_measurement_group(self, self.h5_file)

            for k, v in self.data.items():
                H[k] = v            
            
            self.h5_file.close()

    def setup_figure(self):

        self.ui = load_qt_ui_file(sibling_path(__file__, 'picam_readout.ui'))
        
        self.cam_hw.settings.connected.connect_to_widget(self.ui.hw_connect_checkBox)
        
        self.cam_hw.settings.ExposureTime.connect_to_widget(self.ui.int_time_doubleSpinBox) 
        self.cam_hw.settings.SensorTemperatureReading.connect_to_widget(self.ui.temp_doubleSpinBox) 

        self.activation.connect_to_pushButton(self.ui.start_pushButton)
        self.ui.commit_pushButton.clicked.connect(self.cam_hw.commit_parameters)

        self.settings.save_h5.connect_to_widget(self.ui.save_h5_checkBox)
        self.settings.continuous.connect_to_widget(self.ui.continuous_checkBox)
        self.settings.wl_calib.connect_to_widget(self.ui.wl_calib_comboBox)

        self.settings.background_subtract.connect_to_widget(self.ui.background_subtract_checkBox)
        self.ui.update_background_pushButton.clicked.connect(self.update_background)

        import pyqtgraph.dockarea as dockarea

        self.dockarea = dockarea.DockArea()
        self.ui.plot_groupBox.layout().addWidget(self.dockarea)
        
        self.spec_plot = pg.PlotWidget()
        spec_dock = self.dockarea.addDock(name='Spec', position='below', widget=self.spec_plot)
        self.spec_plot_line = self.spec_plot.plot([1, 3, 2, 4, 3, 5])
        self.spec_plot.enableAutoRange()

        self.img_graphlayout = pg.GraphicsLayoutWidget()
        self.img_plot = self.img_graphlayout.addPlot()
        self.img_item = pg.ImageItem()
        self.img_plot.addItem(self.img_item)
        self.img_plot.showGrid(x=True, y=True)
        self.img_plot.setAspectLocked(lock=True, ratio=1)
        self.dockarea.addDock(name='Img', position='below', relativeTo=spec_dock, widget=self.img_graphlayout)

        self.hist_lut = pg.HistogramLUTItem()
        self.hist_lut.autoHistogramRange()
        self.hist_lut.setImageItem(self.img_item)
        self.img_graphlayout.addItem(self.hist_lut)
        
        self.cam_controls = self.app.hardware['picam'].settings.New_UI(style='scroll_form')
        self.dockarea.addDock(name='PICAM', position='below', relativeTo=spec_dock, widget=self.cam_controls)

        spec_dock.raiseDock()

        """
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
        self.graph_layout.addItem(self.hist_lut)"""

    def update_display(self):
        self.img_item.setImage(self.roi_data[0].T.astype(float), autoLevels=False)
        self.hist_lut.imageChanged(autoLevel=True, autoRange=True)
        
        wl_calib = self.settings['wl_calib']
        x = {'spectrometer':self.wls,
             'pixels':self.pixels,
             'raw_pixels':self.raw_pixels,
             'wave_numbers':self.wave_numbers,
             'raman_shifts':self.raman_shifts }[self.settings['wl_calib']]
                     
        self.spec_plot_line.setData(x, self.spectrum)
        self.spec_plot.setTitle("acq_time: {}".format(self.acq_time))
        
    def get_spectrum(self):
        if hasattr(self, 'spectrum'):
            return self.spectrum  # maybe not be generally true
    
    def get_roi_data(self):
        if hasattr(self, 'roi_data'):
            return self.roi_data  # maybe not be generally true
        
    def get_wavelengths(self):
        if hasattr(self, 'wls'):
            return self.wls
