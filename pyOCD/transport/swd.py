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

from transport import Transport
import logging

DP_REG = {'IDCODE' : 0x00,
          'ABORT' : 0x00,
          'CTRL_STAT': 0x04,
          'WCR' : 0x04,
          'SELECT': 0x08
          }

AP_REG = {'CSW' : 0x00,
          'TAR' : 0x04,
          'DRW' : 0x0C,
          'IDR' : 0xFC
          }

SWD_ACK_OK = 1
SWD_ACK_WAIT = 2
SWD_ACK_FAULT = 4

IDCODE = 0 << 2
AP_ACC = 1 << 0
DP_ACC = 0 << 0
READ = 1 << 1
WRITE = 0 << 1
VALUE_MATCH = 1 << 4
MATCH_MASK = 1 << 5

ORUNERRCLR = 0b100
WDERRCLR   = 0b011
STKERRCLR  = 0b010
STKCMPCLRa = 0b001
DAPABORT   = 0b000

APBANKSEL = 0x000000f0

# AP Control and Status Word definitions
CSW_SIZE     =  0x00000007
CSW_SIZE8    =  0x00000000
CSW_SIZE16   =  0x00000001
CSW_SIZE32   =  0x00000002
CSW_ADDRINC  =  0x00000030
CSW_NADDRINC =  0x00000000
CSW_SADDRINC =  0x00000010
CSW_PADDRINC =  0x00000020
CSW_DBGSTAT  =  0x00000040
CSW_TINPROG  =  0x00000080
CSW_HPROT    =  0x02000000
CSW_MSTRTYPE =  0x20000000
CSW_MSTRCORE =  0x00000000
CSW_MSTRDBG  =  0x20000000
CSW_RESERVED =  0x01000000

CSW_VALUE = (CSW_RESERVED | CSW_MSTRDBG | CSW_HPROT | CSW_DBGSTAT | CSW_SADDRINC)

TRANSFER_SIZE = {8: CSW_SIZE8,
                 16: CSW_SIZE16,
                 32: CSW_SIZE32
                 }



reverse_bits = lambda b,w: ("{0:0%db}" % w).format(b)[::-1]

def get_word(data,i=0,pop=False): 
    d = data[3+i] << 24 | data[2+i] << 16 | data[1+i] << 8 | data[0+i]
    if pop: del d[i:i+4]
    return d


class SWD(Transport):
    def __init__(self, interface):
        super(SWD, self).__init__(interface)
        self.csw = -1
        self.dp_select = -1

    def init(self, frequency=1000000):
        # Flush to be safe
        self.flush()

        # set clock frequency
        # self.protocol.setSWJClock(frequency)

        # configure transfer
        # self.protocol.transferConfigure()

        # switch to SWD mode reset state
        self.JTAG2SWD()

        # clear errors
        self.writeDP(DP_REG['ABORT'], 0x1e)

        # configure swd protocol
        self.writeDP(DP_REG['SELECT'], 1)   # set the CTRLSEL bit to switch
                                            # access from DP.CTRL/STAT to DP.WCR
        self.writeDP(DP_REG['WCR'], 0)      
        self.writeDP(DP_REG['SELECT'], 0)   # switch back to DP.CTRL/STAT


    def JTAG2SWD(self):
        # reset the state machine for JTAG/SWD
        self.interface.write('1'*56)

        # send the 16bit JTAG-to-SWD sequence
        self.interface.write(reverse_bits(0x9EE7,w=16))

        # If we were already in SWD mode, make sure SWD is in reset state
        self.interface.write('1'*56)

        self.interface.write('0'*8)

        # read ID code to confirm synchronization
        logging.info('IDCODE: 0x%X', self.readDP(DP_REG['IDCODE']))

    def _write(self, data):
        parity = data
        parity = (parity ^ (parity >> 16))
        parity = (parity ^ (parity >> 8))
        parity = (parity ^ (parity >> 4))
        parity = (parity ^ (parity >> 2))
        parity = (parity ^ (parity >> 1)) & 1

        # Insert one turnaround period (needed between reception of ACK and
        # transmission of data) followed by the data word and parity bit
        data = '0' + reverse_bits(data,w=32) + ('1' if parity else '0')

        print "WDATA", data
        self.interface.write(data)

    def _read(self):
        # read 32bit word + 1 bit parity, and clock 1 additional cycle to
        # satisfy turnaround for next transmissoin
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
        self.writeDP(DP_REG['SELECT'], 0)            # set SELECT 0
        self.writeDP(DP_REG['CTRL_STAT'], 0x50000000) # set CTRL/STAT CxxxPWRUPREQ
        self.readDP(DP_REG['CTRL_STAT'])             # read CTRL/STAT CxxxPWRUPREQ

        return

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

        # wait 1 TRN then read 3 bit ACK
        ack = self.interface.read(4)
        print 'ACK  ', ack[3:0:-1]
        ack = int(ack[3:0:-1],2)

        if ack != SWD_ACK_OK:
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

    def clearStickyErr(self):
        self.writeDP(DP_REG['ABORT'], STKERRCLR)

    def writeAP(self, addr, data):
        self._request(addr | 0b01)
        self._write(data)
        return True
    
    def writeMem(self, addr, data, transfer_size=32):
        self.writeAP(AP_REG['CSW'], CSW_VALUE | TRANSFER_SIZE[transfer_size])

        if transfer_size == 8:
            data = data << ((addr & 0x03) << 3)
        elif transfer_size == 16:
            data = data << ((addr & 0x02) << 3)

        self.writeAP(AP_REG['TAR'], addr)
        self.writeAP(AP_REG['DRW'], data)

    def readMem(self, addr, transfer_size=32, mode=Transport.READ_NOW):
        self.writeAP(AP_REG['CSW'], CSW_VALUE | TRANSFER_SIZE[transfer_size])
        self.writeAP(AP_REG['TAR'], addr)
        
        resp = self.readAP(AP_REG['DRW'])

        if transfer_size == 8:
            resp = (resp >> ((addr & 0x03) << 3) & 0xff)
        elif transfer_size == 16:
            resp = (resp >> ((addr & 0x02) << 3) & 0xffff)

        return resp

    # write aligned word ("data" are words)
    def writeBlock32(self, addr, data):
        # put address in TAR
        self.writeAP(AP_REG['CSW'], CSW_VALUE | CSW_SIZE32)

        for i in range(len(data)//4):
            self.writeAP(AP_REG['TAR'], addr)
            self.writeAP(AP_REG['DRW'], get_word(data))
            addr += 4

    # read aligned word (the size is in words)
    def readBlock32(self, addr, size):
        self.writeAP(AP_REG['CSW'], CSW_VALUE | CSW_SIZE32)
        
        data = []
        for i in range(size):
            self.writeAP(AP_REG['TAR'], addr)
            data.append(self.readAP(AP_REG['DRW']))
            addr += 4

        return data
