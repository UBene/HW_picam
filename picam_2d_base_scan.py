from ScopeFoundry.scanning.base_raster_slow_scan import BaseRaster2DSlowScan

from .picam_readout import PicamReadoutMeasure


class Picam2DBaseSlowScan(BaseRaster2DSlowScan):

    name = 'hyperspectral_2d_map'

    def setup(self):
        super().setup()
        s = self.settings
        s.New('readout', str, initial='picam_readout',
              choices=('picam_readout',))

        self.ui.device_details_layout.addWidget(
            s.readout.new_default_widget())
        self.ui.device_details_GroupBox.setTitle('readout')

    def setup_figure(self):       
        super().setup_figure()
        choices = [m for m in self.app.measurements.keys() if isinstance(
            self.app.measurements[m], PicamReadoutMeasure)]
        self.settings.readout.change_choice_list(choices)
        self.settings['readout'] = choices[0]
        
        
    def pre_scan_setup(self):
        
        s = self.settings
        self.readout = self.app.measurements[s['readout']]

        rs = self.readout.settings
        self.save_h50 = rs['save_h5']
        rs['save_h5'] = False
        self.cont0 = rs['continuous']
        rs['continuous'] = False

    def collect_pixel(self, pixel_num, k, j, i):

        measure = self.readout
        self.start_nested_measure_and_wait(measure, nested_interrupt=False)

        if pixel_num == 0:
            wls = measure.get_wavelengths()
            self.data_spape = (*self.scan_shape, len(wls))
            if self.settings['save_h5']:
                self.spec_map_h5 = self.h5_meas_group.create_dataset('spec_map',
                                                                     shape=self.data_spape,
                                                                     dtype=float,
                                                                     compression='gzip')
                self.h5_meas_group.create_dataset(
                    'wls',
                    data=wls
                )

        spec = measure.get_spectrum()
        self.display_image_map[k, j, i] = sum(spec)
        if self.settings['save_h5']:
            self.spec_map_h5[k, j, i] = spec

    def post_scan_cleanup(self):
        self.readout.settings['save_h5'] = self.save_h50
        self.readout.settings['continuous'] = self.cont0
