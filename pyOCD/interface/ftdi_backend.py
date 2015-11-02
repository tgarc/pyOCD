"""
 mbed CMSIS-DAP debugger
 Copyright (c) 2006-2013 ARM Limited

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

from interface import Interface
from pyOCD.lib.userconfig import UserConfig

digilent_cfg = UserConfig()
digilent_cfg.FTDI_GPIO_MASK = 0x60a3
digilent_cfg.GPIO_WMASK = 0x60a0
digilent_cfg.GPIO_RMASK = 0x6080
digilent_cfg.CABLE_NAME = 'Digilent USB Device'
digilent_cfg.SHOW_CONFIG = False
digilent_cfg.CABLE_DRIVER = 'ftdi'


class HexNum(int):
    def __str__(self):
        return '0x%04x' % self
    def __repr__(self):
        return '0x%04x' % self


class FTD2xx(Interface):
    def __init__(self, config=digilent_cfg):
        super(FTD2xx, self).__init__()
        self.config = config
        self.driver = None

    def init(self):
        cablemodule = self.config.getcable()
        if self.config.CABLE_NAME is None:
            cablemodule.showdevs()
            raise Exception("FTD2xx Error: Could not open device")

        self.driver = cablemodule.d2xx.FtdiDevice(self.config)
        
    def write(self, data, wlen=None):
        self._clock_out(len(data), self.config.GPIO_WMASK, data)

    def read(self, rlen):
        return self._clock_out(rlen, self.config.GPIO_RMASK)

    def getAllConnectedInterface(vid, pid):
        if_h = FTD2xx(digilent_cfg)
        if_h.vid = vid
        if_h.pid = pid
        if_h.vendor_name = "Digilent"
        if_h.product_name = "HS2"

        return if_h

    def _set_gpio(self, value):
        self.driver.write_gpio(value)

    def _get_gpio(self):
        return HexNum(self.driver.read_gpio())

    g = property(_get_gpio, _set_gpio)

    def _clock_out(self, clklen, gpio_mask, data=None):
        if data is None:
            data = '0'*clklen

        result = []
        for ch in data:
            value = gpio_mask
            value |= 2 if ch == '1' else 0
            self.g = value
            _ = self.g
            g = self.g
            self.g = value | 1
            #print hex(g),str(g)
            result.append('1' if g & 4 else '0')
        return ''.join(result)

    def close(self):
        return self.driver.Close()
