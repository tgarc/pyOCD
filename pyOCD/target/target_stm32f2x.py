from pyOCD.target.cortex_m import CortexM
from pyOCD.target.memory_map import (FlashRegion,RamRegion,MemoryMap)
import logging

DBGMCU_CR = 0xE0042004
DBGMCU_APB1_FZ = 0xE0042008

class STM32F2X(CortexM):
    memoryMap = MemoryMap(
        FlashRegion(start=0x08000000, length=0x10000, blocksize=0x400, isBootMemory=True),
        RamRegion(start=0x20000000, length=0x20000)
        )

    def __init__(self, transport):
        super(STM32F2X, self).__init__(transport, self.memoryMap)

    def init(self):
        logging.debug('stm32f2x init')
        CortexM.init(self)

        # DBGMCU_CR |= DBG_STANDBY | DBG_STOP | DBG_SLEEP
        self.writeMemory(DBGMCU_CR, self.readMemory(DBGMCU_CR) | 0x00000007)

        # Stop watchdog counters during halt
        # DBGMCU_APB1_FZ = DBG_IWDG_STOP | DBG_WWDG_STOP
        self.writeMemory(DBGMCU_APB1_FZ, 0x00001800)
