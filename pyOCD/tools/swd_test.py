#! /usr/bin/env python
'''
Simplistic chain discovery
'''

import sys
import os

os_cmd = sys.argv[0]

from pyOCD.lib.userconfig import UserConfig
from pyOCD.jtag.discover import Chain

config = UserConfig()
config.FTDI_GPIO_MASK = 0x60a3
config.CABLE_NAME = 'Digilent USB Device'
config.CABLE_DRIVER = 'ftdi'
config.SHOW_CONFIG = False
config.readargs(parseargs=True)

cablemodule = config.getcable()

if config.CABLE_NAME is None:
    cablemodule.showdevs()
    raise SystemExit

driver = cablemodule.d2xx.FtdiDevice(config)

if config.SHOW_CONFIG:
    print config.dump()

class HexNum(int):
    def __str__(self):
        return '0x%04x' % self
    def __repr__(self):
        return '0x%04x' % self

class test(object):
    def _set_gpio(self, value):
        driver.write_gpio(value)
    def _get_gpio(self):
        return HexNum(driver.read_gpio())
    g = property(_get_gpio, _set_gpio)
    def clock_out(self,s, start=0x60a0):
        assert not (set(s) - set('01')), s
        result = []
        for ch in s:
            value = start
            value |= 2 if ch == '1' else 0
            self.g = value
            _ = self.g
            g = self.g
            self.g = value | 1
            #print hex(g),str(g)
            result.append('1' if g & 4 else '0')
        return ''.join(result)

    def clock_in(self, s):
        return self.clock_out(s, 0x6080)

    def check(self):
        self.write(2,0)          # set SELECT 0
        self.write(1,0x50000000) # set CTRL/STAT CxxxPWRUPREQ
        self.read(1)             # read CTRL/STAT CxxxPWRUPREQ

    def reset(self):
        self.clock_out(64 * '1' + 64 * '0')

    def read(self, regnum):
        assert 0 <= regnum <= 7
        parity = (regnum ^ (regnum >> 1) ^ (regnum >> 2) ^ 1) & 1
        print self.clock_out('1%s1%s%s%s01' % (
                  '01'[bool(regnum & 4)],
                  '01'[bool(regnum & 1)],
                  '01'[bool(regnum & 2)],
                  '01'[parity]))
        x = self.clock_in(38 * '0')
        print x
        value = int(''.join(reversed(x[4:36])), 2)
        parity = value
        parity = (parity ^ (parity >> 16))
        parity = (parity ^ (parity >> 8))
        parity = (parity ^ (parity >> 4))
        parity = (parity ^ (parity >> 2))
        parity = (parity ^ (parity >> 1)) & 1
        parity ^= x[36] == '1'
        print 'Result = %08x Parity Fault = %d' % (value, parity)
        return value, parity

    def write(self, regnum, value):
        assert 0 <= regnum <= 7
        parity = (regnum ^ (regnum >> 1) ^ (regnum >> 2)) & 1
        print self.clock_out('1%s0%s%s%s01' % (
                  '01'[bool(regnum & 4)],
                  '01'[bool(regnum & 1)],
                  '01'[bool(regnum & 2)],
                  '01'[parity]))
        print self.clock_in(5 * '0')
        parity = value
        parity = (parity ^ (parity >> 16))
        parity = (parity ^ (parity >> 8))
        parity = (parity ^ (parity >> 4))
        parity = (parity ^ (parity >> 2))
        parity = (parity ^ (parity >> 1)) & 1
        value = '{0:032b}'.format(value)
        value = ''.join(reversed(value))
        print self.clock_out('%s%s' % (value, parity))

d = test()

if __name__ == '__main__':
    d.check()
