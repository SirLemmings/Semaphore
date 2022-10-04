import config as cfg
import blocks as bk
import json
import os
import syncing as sy
import hashlib
from bidict import bidict


def load_block_data(block):
    """send block data to memory"""
    epoch = block.epoch_timestamp
    cfg.blocks[epoch] = block
    cfg.hashes[epoch] = block.block_hash
    print(epoch)
    print(block.block_index)
    print()
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
    sy.request_history()


def sync_func(blocks):
    cfg.staged_sync_blocks = []
    i = 0
    for block in blocks:
        i += 1
        epoch = block.epoch_timestamp
        if epoch in cfg.temp_epochs:
            break
        print("received")
        load_block_data(block)
        dump = json.dumps(block.convert_to_dict())
        name = os.path.join(f"./{cfg.ALIAS}", f"{epoch}.json")
        with open(name, "wb") as f:
            f.write(dump.encode("utf-8"))
    i = 0
    # print('ind',cfg.indexes)
    for block in [cfg.temp_blocks[epoch] for epoch in cfg.temp_epochs]:
        i += 1
        block.update_index()
        epoch = block.epoch_timestamp
        print("built")
        load_block_data(block)
        dump = json.dumps(block.convert_to_dict())
        name = os.path.join(f"./{cfg.ALIAS}", f"{epoch}.json")
        with open(name, "wb") as f:
            f.write(dump.encode("utf-8"))

    cfg.activation_epoch = cfg.current_epoch + cfg.FORWARD_SLACK_EPOCHS * cfg.EPOCH_TIME
    cfg.synced = True

    # print("111111")
    # print(cfg.epochs)
    # print(cfg.indexes)
    for epoch in cfg.epoch_processes.keys():
        i = epoch - (cfg.DELAY) * cfg.EPOCH_TIME
        # print('ep',epoch)
        while True:
            # print('i',i)
            if i in cfg.indexes:
                # print('ok^')
                break
            i -= cfg.EPOCH_TIME
        index = cfg.indexes[i] + 1
        # print('index',index)
        epochs = cfg.epochs[index - cfg.DELAY : index]
        cfg.epoch_chain_commit[epoch] = chain_commitment(
            epoch, epochs=epochs, origin="ep"
        )
        # print(cfg.epoch_chain_commit[epoch])
        # print()
    cfg.temp_blocks = {}
    cfg.temp_epochs = []
    cfg.temp_hashes = bidict({})
    print("***SYNCED***")
    print("epochs", cfg.epochs)


def chain_commitment(epoch, epochs=cfg.epochs, hashes=cfg.hashes, origin=None):
    if origin == "ep":
        print("cc info")
        print(epochs)
        print(cfg.epochs)
    earliest_process_epoch = (
        cfg.current_epoch
        - (cfg.SLACK_EPOCHS + cfg.VOTE_MAX_EPOCHS + cfg.SYNC_EPOCHS) * cfg.EPOCH_TIME
    )
    last_commit_epoch = epoch - cfg.DELAY * cfg.EPOCH_TIME

    if last_commit_epoch > earliest_process_epoch:
        raise Exception("insufficient blocks confirmed")

    committed_hashes = [hashes[i] for i in epochs[-cfg.DELAY :]]

    chain_commitment = hash_commitments(committed_hashes)
    diff = int((epoch - epochs[-1]) / cfg.EPOCH_TIME) % cfg.DELAY
    chain_commitment += f"{diff:02d}"
    if origin == "ep":
        print("cc info2")
        print(epochs)
        print(cfg.epochs)
        print(epochs[-cfg.DELAY :], epoch)
        print(chain_commitment)
    return chain_commitment


def hash_commitments(committed_hashes):
    if len(committed_hashes) != cfg.DELAY:
        raise Exception(
            f"committed_hashes not of length {cfg.DELAY}. got length of {len(committed_hashes)}"
        )
    commitment = ""
    for com_hash in committed_hashes:
        commitment += com_hash
    return hashlib.sha256(commitment.encode()).hexdigest()
