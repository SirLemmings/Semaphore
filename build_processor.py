import blocks as bk
import consensus as cs
import blocks as bk
import config as cfg

class BuildProcessor:
    def __init__(self, epoch, broadcasts):
        self.epoch = epoch
        self.broadcasts = broadcasts
        if self.broadcasts is not None and len(self.broadcasts)>0:
            self.block = bk.Block(self.broadcasts, self.epoch)
        else:
            print("~EMPTY EPOCH")
            self.block = None

    def finalize_block(self):
        """add final block to chain"""
        if self.block is None:
            return
        cs.add_block(self.block, self.epoch)
        if cfg.SHOW_BLOCK_INFO:
            print("~block_hash:", self.block.block_hash)
            print(
                "~block_engagements:",
                len(self.block.bc_body) if self.block.bc_body != "None" else 0,
            )