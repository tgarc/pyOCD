#! /usr/bin/env python
'''
Simplistic chain discovery
'''

import sys
import os

os_cmd = sys.argv[0]

root = os.path.join(os.path.dirname(__file__), '../..')
sys.path.insert(0, root)

from playtag.lib.userconfig import UserConfig
from playtag.jtag.discover import Chain

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
            self.g = value | 1
            g = self.g
            #print hex(g),str(g)
            result.append('1' if g & 4 else '0')
        return ''.join(result)

    def clock_in(self, s):
        return self.clock_out(s, 0x6080)

    def check(self):
        fmt = (64*'0' + '1{0:07b}').format
        for i in range(128):
            print ' ', i, '\r',
            sys.stdout.flush()
            x = fmt(i)
            y = self.clock_out(x)
            z = self.clock_in(64*'1')
            if z != 64*'1':
                print
                print x
                print y, z
                print
d = test()

d.check()
