import blocks as bk
import consensus as cs
import blocks as bk
import config as cfg


class BuildProcessor:
    def __init__(self, epoch, broadcasts, sync_commit):
        self.epoch = epoch
        self.broadcasts = broadcasts
        self.empty_commit = sync_commit
        self.block = None
        if self.broadcasts is not None and len(self.broadcasts) > 0:
            self.block = bk.Block(self.broadcasts, self.epoch)
        else:
            print("~EMPTY EPOCH")
            if self.empty_commit is None:
                if epoch in cfg.epoch_chain_commit:
                    self.empty_commit = cfg.epoch_chain_commit[epoch]

    def finalize_block(self):
        """add final block to chain"""
        if self.block is None:
            #this adds to both, which is unnecessary
            cfg.hashes[self.epoch] = self.empty_commit
            cfg.temp_hashes[self.epoch] = self.empty_commit
            return
        cs.add_block(self.block, self.epoch)
        if cfg.SHOW_BLOCK_INFO:
            print(
                f"~block_hash: {self.block.block_hash[:4]}/{self.block.block_hash[-4:]}"
            )
            print(
                "~block_engagements:",
                len(self.block.bc_body) if self.block.bc_body != "None" else 0,
            )
