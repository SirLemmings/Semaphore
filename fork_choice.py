import config as cfg
import communications as cm
import consensus as cs
import blocks as bk
import timing as tm
from process import Process
import ast
import os
import json

reorg_processes = set()


def request_fork_history(alias):
    print("~requesting fork")
    index = cfg.MINIMUM_REORG_DEPTH
    past_epochs = []
    while True:
        try:
            past_epochs.append(cfg.epochs[-index])
            index *= 2
        except:
            break

    past_hashes = [
        cfg.hashes[epoch] for epoch in past_epochs if epoch > cfg.DELAY * 2 - 2
    ]
    Process(
        1,
        format_fork_request,
        conclude_fork_process,
        "fork_request",
        (past_hashes, past_epochs),
        True,
        specific_peers=[alias],
    )


def fulfill_fork_request(alias, query_id, past):
    print("~fulfilling fork")
    if cfg.activated:
        if (
            len(past[0]) > 0
        ):  # sometimes peer does not send any epochs because there arent enough epochs. this handles that case. might be worth fixing on the other end
            past_hashes = past[0]
            past_epochs = past[1]
            if past_hashes[0] in cfg.hashes.values():
                print("reorg not deep enough")
                return
        else:
            past_hashes = past[0]
            past_epochs = past[0]
        index = cfg.DELAY * 2 - 2
        
        #TODO pretty sure this works right but actually dont know for sure
        for block_hash in past_hashes[1:]:
            print("~index", index)
            print(print("~start epoch", cfg.epochs[index]))
            if block_hash in cfg.epoch_chain_commit.keys():
                shared_epoch = past_epochs[past_hashes.index(block_hash)]
                if cfg.hashes[shared_epoch] != block_hash:
                    print("hash/epoch dont match")
                    return
                index = cfg.epochs.index(shared_epoch)
                break

        history_epochs = cfg.epochs[index:]
        print('~epochs',cfg.epochs)
        print("~index", index)
        print("~start epoch", cfg.epochs[index])
        history_blocks = []
        for epoch in history_epochs:
            block = cfg.blocks[epoch]
            if type(block) is str:
                history_blocks.append(block)
            else:
                history_blocks.append(block.convert_to_dict())
        print("fulfilled fork successfully")
        cm.send_peer_message(alias, f"query_fulfillment|{query_id}|{history_blocks}")
    else:
        print("not activated. delaying fork fulfillment")


def format_fork_request(query, response):
    print("~formatting fork")
    received_blocks = ast.literal_eval(response)
    if type(received_blocks) is list:
        for block in received_blocks:
            if type(block) is not dict and block != "GENESIS":
                return
        return received_blocks


def conclude_fork_process(process):
    print("~concluding fork")
    blocks = process.cached_responses[0]
    for block in blocks:
        if type(block) is bk.Block:
            if not block.check_block_valid():
                print("bad block")
                return

    for block in blocks:
        last_common_epoch = cfg.DELAY * 2 - 2
        if block == "GENESIS":
            blocks = blocks[1:]
            continue
        block = bk.Block(init_dict=block)
        epoch = block.epoch_timestamp
        block_hash = block.block_hash
        try:
            if cfg.hashes[epoch] == block_hash:
                blocks = blocks[1:]
                last_common_epoch = epoch
            else:
                break
        except KeyError:
            break

    swap = compare_weight(blocks.copy(), last_common_epoch)
    print("~SWAP", swap)
    if swap:
        print("***REORG***")
        tm.deactivate()
        remove_history(last_common_epoch)
        for block in blocks:
            block = bk.Block(init_dict=block)
            epoch = block.epoch_timestamp
            if epoch >= cfg.current_epoch - cfg.MINIMUM_REORG_DEPTH:
                break
            cs.load_block_data(block)
            dump = json.dumps(block.convert_to_dict())
            name = os.path.join(f"./{cfg.ALIAS}", f"{epoch}.json")
            with open(name, "wb") as f:
                f.write(dump.encode("utf-8"))
        cfg.initialized = True
        cfg.enforce_chain = True
        global reorg_processes
        reorg_processes = set()
    else:
        print("~no reorg")


def remove_history(last_common_epoch):
    print('bef',cfg.epochs[:15])
    index = cfg.epochs.index(last_common_epoch) + 1
    for epoch in cfg.epochs[index:]:
        if cfg.blocks[epoch] == "GENESIS":
            index+=1
            continue
        del cfg.blocks[epoch]
        del cfg.hashes[epoch]
        del cfg.indexes[epoch]
        name = os.path.join(f"./{cfg.ALIAS}", f"{epoch}.json")
        os.remove(name)
    cfg.epochs = cfg.epochs[:index]
    print('aft',cfg.epochs[:15])
    


def compare_weight(alt_blocks, last_common_epoch):
    current_blocks = [
        block
        for block in [
            cfg.blocks[epoch]
            for epoch in cfg.epochs[cfg.epochs.index(last_common_epoch) + 1 :]
        ]
        if block != "GENESIS"
    ]

    alt_blocks = [bk.Block(init_dict=block) for block in alt_blocks]
    if len(alt_blocks) == 0 or len(current_blocks) == 0:
        print("~uhhhhh", len(alt_blocks), len(current_blocks))
        return

    chain_engagements_alt = set()
    chain_engagements_current = set()
    shallow_block_alt = alt_blocks.pop(-1)
    time_alt = shallow_block_alt.epoch_timestamp
    shallow_block_current = current_blocks.pop(-1)
    time_current = shallow_block_current.epoch_timestamp

    while True:
        if time_current > time_alt:
            pre_engagements = shallow_block_current.get_block_engagements()
            pre_engagements -= chain_engagements_alt
            chain_engagements_current = chain_engagements_current.union(pre_engagements)
            if len(current_blocks) == 0:
                time_current = -1
            else:
                shallow_block_current = current_blocks.pop(-1)
                time_current = shallow_block_current.epoch_timestamp

        elif time_alt > time_current:
            pre_engagements = shallow_block_alt.get_block_engagements()
            pre_engagements -= chain_engagements_current
            chain_engagements_alt = chain_engagements_alt.union(pre_engagements)
            if len(alt_blocks) == 0:
                time_alt = -1
            else:
                shallow_block_alt = alt_blocks.pop(-1)
                time_alt = shallow_block_alt.epoch_timestamp

        else:
            current_pre_engagements = shallow_block_current.get_block_engagements()
            current_pre_engagements -= chain_engagements_alt
            alt_pre_engagements = shallow_block_alt.get_block_engagements()
            alt_pre_engagements -= chain_engagements_current
            chain_engagements_current = chain_engagements_current.union(
                current_pre_engagements
            )
            chain_engagements_alt = chain_engagements_alt.union(alt_pre_engagements)
            if len(current_blocks) == 0:
                time_current = -1
            else:
                shallow_block_current = current_blocks.pop(-1)
                try:
                    time_current = shallow_block_current.epoch_timestamp
                except Exception as e:
                    print(shallow_block_current)
                    print(e)

            if len(alt_blocks) == 0:
                time_alt = -1
            else:
                shallow_block_alt = alt_blocks.pop(-1)
                time_alt = shallow_block_alt.epoch_timestamp

        if time_current == -1 and time_alt == -1:
            break

    print(
        f"~alternate_weight: {len(chain_engagements_alt)}, current_weight: {len(chain_engagements_current)}"
    )
    return len(chain_engagements_alt) > len(chain_engagements_current)
