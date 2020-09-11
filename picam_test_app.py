from ScopeFoundry import BaseMicroscopeApp
from ScopeFoundryHW.picam import PicamHW, PicamReadoutMeasure

class PICAMTestApp(BaseMicroscopeApp):
    
    name = 'picam_test_app'
    
    def setup(self):
        hw = self.add_hardware(PicamHW(self))
        
        self.add_measurement(PicamReadoutMeasure(self))
        
                
if __name__ == '__main__':
    import sys
    app = PICAMTestApp(sys.argv)
    app.exec_()