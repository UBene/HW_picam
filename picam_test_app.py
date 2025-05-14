"""
Created on Aug 4, 2020

@author: Edward Barnard
"""

import logging
import sys

from ScopeFoundry.base_app import BaseMicroscopeApp

logging.basicConfig(level=logging.INFO)


class PicamTestApp(BaseMicroscopeApp):

    name = "picam_test_app"

    def setup(self):

        from ScopeFoundryHW.picam import PicamHW, PicamReadoutMeasure
        from ScopeFoundryHW.picam.picam_polling import PicamPolling

        self.add_hardware(PicamHW(self))
        self.add_measurement(PicamReadoutMeasure(self))

        self.add_measurement(PicamPolling(self))

        # Add a second Picam camera
        # self.add_hardware(PicamHW(self, name='pylon'))
        # self.add_measurement(PicamReadoutMeasure(self, 'pylon'))

        # self.add_measurement(PICAM2DSlowScan(self))


if __name__ == "__main__":
    app = PicamTestApp(sys.argv)
    sys.exit(app.exec_())
