'''
Created on Aug 4, 2020

@author: Edward Barnard

updated 2022-02-13
'''

from ScopeFoundry.base_app import BaseMicroscopeApp


class PicamTestApp(BaseMicroscopeApp):
    
    name = 'picam_test_app'

    def setup(self):

        # Add Hardware components
        from ScopeFoundryHW.picam import PicamHW
        self.add_hardware(PicamHW(self))

        # Add Measurement components
        from ScopeFoundryHW.picam import PicamReadoutMeasure
        self.add_measurement(PicamReadoutMeasure(self))

        from ScopeFoundryHW.pi_spec import PISpectrometerHW
        self.add_hardware(PISpectrometerHW(self))

        
if __name__ == '__main__':
    
    import sys
    app = PicamTestApp(sys.argv)
    sys.exit(app.exec_())
    
