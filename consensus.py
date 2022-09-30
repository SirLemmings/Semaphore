import config as cfg
import blocks as bk
import json
import os
import syncing as sy


def load_block_data(block):
    """send block data to memory"""
    epoch = block.epoch_timestamp
    cfg.blocks[epoch] = block
    cfg.hashes[epoch] = block.block_hash
    print('~new index', epoch,block.block_index)
    cfg.indexes[epoch] = block.block_index
    
    cfg.epochs.append(epoch)
    if epoch not in cfg.epoch_chain_commit:
        cfg.epoch_chain_commit.forceput(epoch, block.chain_commitment)
    for epoch in cfg.chain_commit_offset:
        if cfg.chain_commit_offset[epoch] > 0:
            cfg.chain_commit_offset[epoch] -= 1


def temp_load_block_data(block):
    """send block data to memory"""
    epoch = block.epoch_timestamp
    cfg.temp_blocks[epoch] = block
    cfg.temp_hashes[epoch] = block.block_hash
    cfg.temp_epochs.append(epoch)

    for epoch in cfg.chain_commit_offset:
        if cfg.chain_commit_offset[epoch] > 0:
            cfg.chain_commit_offset[epoch] -= 1


def load_staged_updates():
    if cfg.synced:
        # TODO this should only ever be one block. i dont think it needs the loop
        for block in cfg.staged_block_updates:
            load_block_data(block)
    else:
        for block in cfg.staged_block_updates:
            temp_load_block_data(block)
    cfg.sync_blocks_staged = False
    cfg.staged_block_updates = []



def stage_history_update(block,):
    """updates to make to block data at end of epoch"""
    cfg.staged_block_updates.append(block)


def add_block(block, epoch):
    """add a block to the chain"""
    block_epoch = block.epoch_timestamp

    if cfg.synced:
        block.update_index()
        # ***SANITY CHECK***
        if epoch >= cfg.activation_epoch or epoch != block_epoch:
            if epoch != block_epoch:
                print(f"something went very very wrong: epochs dont match")
            if block.chain_commitment != cfg.epoch_chain_commit[epoch]:
                print("~AAA", block.chain_commitment, block.epoch_timestamp)
                print("~BBB", cfg.epoch_chain_commit.inverse[epoch], epoch)
                print(
                    f"!!!!!!something went very very wrong: chain commitments dont match"
                )

        dump = json.dumps(block.convert_to_dict())
        name = os.path.join(f"./{cfg.ALIAS}", f"{epoch}.json")
        with open(name, "wb") as f:
            f.write(dump.encode("utf-8"))

    stage_history_update(block)


def sync():
    print("~2 request")
    sy.request_history()


def sync_func(blocks):
    cfg.staged_sync_blocks = []
    i = 0
    for block in blocks:
        i += 1
        epoch = block.epoch_timestamp
        if epoch in cfg.temp_epochs:
            break
        load_block_data(block)
        dump = json.dumps(block.convert_to_dict())
        name = os.path.join(f"./{cfg.ALIAS}", f"{epoch}.json")
        with open(name, "wb") as f:
            f.write(dump.encode("utf-8"))
    i = 0
    print(cfg.indexes)
    for block in [cfg.temp_blocks[epoch] for epoch in cfg.temp_epochs]:
        i += 1
        block.update_index()
        epoch = block.epoch_timestamp
        load_block_data(block)
        dump = json.dumps(block.convert_to_dict())
        name = os.path.join(f"./{cfg.ALIAS}", f"{epoch}.json")
        with open(name, "wb") as f:
            f.write(dump.encode("utf-8"))

    cfg.activation_epoch = (
        cfg.current_epoch + cfg.FORWARD_SLACK_EPOCHS * cfg.EPOCH_TIME
    )
    cfg.synced = True
    for epoch in cfg.epoch_processes.keys():
        cfg.epoch_chain_commit[epoch] = cfg.chain_commitment(epoch)
    print("***SYNCED***")

