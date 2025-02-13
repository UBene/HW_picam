import numpy as np
import pyqtgraph as pg
import pyqtgraph.dockarea as dockarea

from ScopeFoundry import Measurement, h5_io
from ScopeFoundry.helper_funcs import load_qt_ui_file, sibling_path

WL_CALIB_CHOICES = ('pixels', 'spectrometer')
X_AXIS_CHOICES = ('pixels', 'raw_pixels', 'wavelengths',
                    'wave_numbers', 'raman_shifts')


class PicamReadoutMeasure(Measurement):

    name = "picam_readout"

    def __init__(self, app, hw_name='picam', name=None):
        self.cam_hw_name = hw_name
        name = f"{hw_name}_readout" if name is None else name
        super().__init__(app, name)

    def setup(self):
        s = self.settings
        s.New('save_h5', bool, initial=False)
        s.New('continuous', bool, initial=True)
        s.New('wl_calib', str, initial='spectrometer', choices=WL_CALIB_CHOICES)
        s.New('laser_wl', initial=532.0, vmin=1e-15, unit='nm',
              description='used to calculate raman_shifts')
        s.New('count_rate', float, unit='Hz')
        s.New('spec_hw', str, initial='pi_spectrometer',
              choices=('pi_spectrometer',
                       'acton_spectrometer'))
        s.New('flip_x', bool, initial=False)
        s.New('flip_y', bool, initial=False)
        s.New('background_subtract', bool, initial=False)
        s.New('x_axis', str, initial='wavelengths', choices=X_AXIS_CHOICES)

        self.display_update_period = 0.050  # seconds
        self.cam_hw = self.app.hardware[self.cam_hw_name]
        self.wls = np.arange(512) + 1  # initialize dummy wls
        self.background = np.zeros_like(self.wls)
        self.spectrum = np.sin(self.wls)
        self.add_operation('update_background', self.update_background)
        self.data = {'spectrum': self.spectrum,
                     'wavelengths': self.wls,
                     'wave_numbers': 1 / self.wls,
                     'raman_shifts': self.wls}

    def read_images(self, readout_count=1, readout_timeout=-1):
        '''read_roi_data returns an image for each roi, so this function returns a list of images.'''
        images = self.cam_hw.cam.read_roi_data(readout_count, readout_timeout)
        if self.settings['flip_x']:
            images = np.flip(images, axis=-1)
        if self.settings['flip_y']:
            images = np.flip(images, -2)
        return images

    def read_spectrum(self, readout_count=1, readout_timeout=-1):
        images = self.read_images(readout_count, readout_timeout)
        return np.average(images[0], axis=0)

    def update_background(self):
        print(self.name, 'start updating background',
              5 * self.cam_hw.settings['ExposureTime'] / 1000, 's')
        self.background = self.read_spectrum(readout_count=5)
        self.settings['background_subtract'] = True
        print(self.name, 'background updated')

    def run(self):
        hw = self.cam_hw
        cam = self.cam_hw.cam
        cam.commit_parameters()

        s = self.settings
        cam_s = self.cam_hw.settings

        while not self.interrupt_measurement_called:
            image = self.read_images(readout_timeout=max(60_000, int(cam_s["ExposureTime"] * 1.1)))[0]
            spectrum = np.average(image, axis=0)

            if s['background_subtract']:
                spectrum -= self.background

            px_index = np.arange(spectrum.shape[-1])
            binning = cam_s['roi_x_bin']
            binning = binning if binning else 1
            
            wls = binning * px_index + 0.5 * (binning - 1) + 1
            if s['wl_calib'] == 'spectrometer':
                hw = self.app.hardware[s['spec_hw']]
                wls = hw.get_wl_calibration(px_index, binning, m_order=1, pixel_width=cam_s['PixelWidth'])
            else:
                s['x_axis'] = 'pixels'

            s['count_rate'] = spectrum.sum() / (cam_s['ExposureTime'] / 1000.0)
            self.spectrum = self.data['spectrum'] = spectrum
            self.wls = self.data['wavelengths'] = wls
            self.data['wave_numbers'] = 1.0e7 / wls
            self.data['raman_shifts'] = 1.0e7 / s['laser_wl'] - 1.0e7 / wls
            self.data['pixels'] = binning * px_index + 0.5 * (binning - 1)
            self.data['raw_pixels'] = px_index
            self.data['image'] = image
            self.wls_mean = wls.mean()

            if not s['continuous']:
                break

        if s['save_h5']:
            self.save_h5()

    def save_h5(self):
        h5_file = h5_io.h5_base_file(self.app, measurement=self)
        meas_group = h5_io.h5_create_measurement_group(self, h5_file)
        for k, v in self.data.items():
            meas_group[k] = v
        h5_file.close()

    def setup_figure(self):
        self.ui = load_qt_ui_file(sibling_path(__file__, 'picam_readout.ui'))
        self.cam_hw.settings.connected.connect_to_widget(
            self.ui.hw_connect_checkBox)
        self.cam_hw.settings.ExposureTime.connect_to_widget(
            self.ui.int_time_doubleSpinBox)

        self.activation.connect_to_pushButton(self.ui.start_pushButton)

        self.settings.save_h5.connect_to_widget(self.ui.save_h5_checkBox)
        self.settings.continuous.connect_to_widget(self.ui.continuous_checkBox)
        self.settings.x_axis.connect_to_widget(self.ui.x_axis_comboBox)

        self.settings.background_subtract.connect_to_widget(
            self.ui.background_subtract_checkBox)
        self.ui.update_background_pushButton.clicked.connect(
            self.update_background)

        self.dockarea = dockarea.DockArea()
        self.ui.plot_groupBox.layout().addWidget(self.dockarea)

        self.spec_plot = pg.PlotWidget()
        self.spec_plot_line = self.spec_plot.plot([1, 3, 2, 4, 3, 5])
        self.spec_plot.enableAutoRange()

        self.img_graphlayout = pg.GraphicsLayoutWidget()
        self.img_plot = self.img_graphlayout.addPlot()
        self.img_item = pg.ImageItem()
        self.img_plot.addItem(self.img_item)
        self.img_plot.showGrid(x=True, y=True)
        self.img_plot.setAspectLocked(lock=True, ratio=1)
        self.hist_lut = pg.HistogramLUTItem()
        self.hist_lut.autoHistogramRange()
        self.hist_lut.setImageItem(self.img_item)
        self.img_graphlayout.addItem(self.hist_lut)
        self.cam_controls = self.cam_hw.New_UI()

        spec_dock = self.dockarea.addDock(
            name='Spec', position='below', widget=self.spec_plot)
        self.dockarea.addDock(name='Img', position='below',
                              relativeTo=spec_dock, widget=self.img_graphlayout)
        self.dockarea.addDock(name=self.cam_hw_name, position='below',
                              relativeTo=spec_dock, widget=self.cam_controls)
        spec_dock.raiseDock()

    def update_display(self):
        image = self.data['image'].T.astype(float)
        self.img_item.setImage(image, autoLevels=False)
        self.hist_lut.imageChanged(autoLevel=True, autoRange=True)

        x = self.data[self.settings['x_axis']]
        y = self.data['spectrum']
        self.spec_plot_line.setData(x, y)

    def get_spectrum(self):
        return self.data['spectrum']
    
    def get_image(self):
        return self.data['image']
    
    def get_wavelengths(self):
        return self.data['wavelengths']
    
    def New_quick_UI(self, operations=['show_ui']):
        from qtpy import QtWidgets
        widget = QtWidgets.QGroupBox(title=self.name)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(self.cam_hw.settings.New_UI(include=('connected',)))
        widget.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                             QtWidgets.QSizePolicy.Maximum)
        show_ui_btn = QtWidgets.QPushButton('show ui')
        show_ui_btn.clicked.connect(self.show_ui)
        layout.addWidget(show_ui_btn)
        # for op in operations:
        #     layout.addWidget(self.new_operation_push_buttons(op))
        return widget   

    def New_mini_UI(self):
        from qtpy.QtWidgets import QWidget, QHBoxLayout, QSizePolicy, QPushButton
        widget = QWidget()
        layout = QHBoxLayout(widget)
        widget.setSizePolicy(QSizePolicy.MinimumExpanding,
                             QSizePolicy.Minimum)
        cb = self.cam_hw.settings.connected.new_default_widget()
        cb.setText(f'connect {self.cam_hw_name}')
        layout.addWidget(cb)
        show_ui_btn = QPushButton('show ui')
        show_ui_btn.clicked.connect(self.show_ui)
        layout.addWidget(show_ui_btn)
        return widget 
