#! /usr/bin/env python
'''
Simplistic chain discovery
'''


from pyOCD.lib.userconfig import UserConfig
from pyOCD.jtag.discover import Chain
from pyOCD.transport.transport import Transport
from pyOCD.interface.interface import Interface

DP_REG = {'IDCODE' : 0x00,
          'ABORT' : 0x00,
          'CTRL_STAT': 0x04,
          'SELECT': 0x08
          }
AP_REG = {'CSW' : 0x00,
          'TAR' : 0x04,
          'DRW' : 0x0C,
          'IDR' : 0xFC
          }

DAP_TRANSFER_OK = 1
DAP_TRANSFER_WAIT = 2
DAP_TRANSFER_FAULT = 4


reverse_bits = lambda b,w: ("{0:0%db}" % w).format(b)[::-1]

class HexNum(int):
    def __str__(self):
        return '0x%04x' % self
    def __repr__(self):
        return '0x%04x' % self


# eventually, the FTD2xx driver will be separate from the DigilentHS2
# class so libFTDI support can be added
class DigilentHS2(Interface):
    GPIO_RMASK = 0x6080
    GPIO_WMASK = 0x60a0

    config = UserConfig()
    config.FTDI_GPIO_MASK = 0x60a3
    config.CABLE_NAME = 'Digilent USB Device'
    config.SHOW_CONFIG = False

    def __init__(self, driver='ftdi'):
        super(DigilentHS2, self).__init__()

        self.config.CABLE_DRIVER = driver
        cablemodule = self.config.getcable()
        if self.config.CABLE_NAME is None:
            cablemodule.showdevs()
            raise Exception("FTD2xx Error: Could not open device")

        self.driver = cablemodule.d2xx.FtdiDevice(self.config)
        
    def write(self, data, wlen=None):
        self._clock_out(len(data), DigilentHS2.GPIO_WMASK, data)

    def read(self, rlen):
        return self._clock_out(rlen, DigilentHS2.GPIO_RMASK)

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


class SWD(Transport):
    def __init__(self, interface):
        super(SWD, self).__init__(interface)

    def _write(self, data):
        parity = data
        parity = (parity ^ (parity >> 16))
        parity = (parity ^ (parity >> 8))
        parity = (parity ^ (parity >> 4))
        parity = (parity ^ (parity >> 2))
        parity = (parity ^ (parity >> 1)) & 1

        data = reverse_bits(data,w=32) + ('1' if parity else '0')

        print "WDATA", data
        self.interface.write(data)

    def _read(self):
        x = self.interface.read(34)
        print "RDATA", x[31::-1]
        data, presp = int(x[31::-1], 2), int(x[32], 2)

        parity = data
        parity = (parity ^ (parity >> 16))
        parity = (parity ^ (parity >> 8))
        parity = (parity ^ (parity >> 4))
        parity = (parity ^ (parity >> 2))
        parity = (parity ^ (parity >> 1)) & 1

        if parity ^ presp:
            raise ValueError("Parity Error")

        return data

    def check(self):
        self.connect()

        self.writeDP(DP_REG['SELECT'], 0)            # set SELECT 0
        self.writeDP(DP_REG['CTRL_STAT'], 0x50000000) # set CTRL/STAT CxxxPWRUPREQ
        self.readDP(DP_REG['CTRL_STAT'])             # read CTRL/STAT CxxxPWRUPREQ

        return

    def connect(self):
        self._reset()
        
    def _reset(self):
        self.interface.write(64 * '1' + 64 * '0')

    def _request(self, rqst):
        """
        Sends an SWD 4 bit request packet (APnDP | RnW | A[2:3]) and
        verifies the response from the target
        """
        parity = rqst
        parity ^= parity >> 1
        parity ^= parity >> 2        
        parity &= 1

        rqst = '1{}{}01'.format(reverse_bits(rqst,w=4), '1' if parity else '0')
        print 'RQST ', rqst
        self.interface.write(rqst)

        ack = self.interface.read(4)
        print 'ACK  ', ack[3:0:-1]
        ack = int(ack[3:0:-1],2)

        if ack != DAP_TRANSFER_OK:
            raise Transport.TransferError('Received invalid ACK (0b{:03b})'.format(ack))

        return ack

    def readDP(self, addr, mode=Transport.READ_NOW):
        self._request(addr | 0b10)
        return self._read()

    def writeDP(self, addr, data):
        self._request(addr | 0b00)
        self._write(data)
        return True

    def readAP(self, addr, mode=Transport.READ_NOW):
        self._request(addr | 0b11)
        return self._read()

    def writeAP(self, addr, data):
        self._request(addr | 0b01)
        self._write(data)
        return True
    

if __name__ == '__main__':
    SWD(DigilentHS2())().check()
