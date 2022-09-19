# Author: Alex Dulisse
# Version: 0.4.1

import blocks as bk
import consensus as cs
import blocks as bk
# import timing as tm
import config as cfg

from process import Process

class BuildProcessor:
    def __init__(self, epoch, broadcasts):
        self.epoch = epoch
        self.broadcasts = broadcasts

        if self.broadcasts is not None and len(self.broadcasts)>0:
            self.block = bk.Block(self.broadcasts, self.epoch)
        else:
            print("~EMPTY BLOCK")
            self.block = None#bk.Block({}, self.epoch)

    def finalize_block(self):
        """add final block to chain"""
        if self.block is None:
            return
        cs.add_block(self.block, self.epoch)
        if cfg.SHOW_BLOCK_INFO:
            print("~hash", self.block.block_hash)
            # print("~bkep", self.block["epoch_timestamp"])
            print(
                "~len ",
                len(self.block.bc_body) if self.block.bc_body != "None" else 0,
            )