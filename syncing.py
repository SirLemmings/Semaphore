# Author: Alex Dulisse
# Version: 0.4.1

from process import Process
import config as cfg
import blocks as bk
import communications as cm
import consensus as cs
import ast
import os
import json


def request_history():
    chain_tip_epoch = cfg.epochs[-1]
    chain_tip_hash = cfg.hashes[chain_tip_epoch]
    Process(
        1,
        format_history_response,
        conclude_history_process,
        "history_request",
        (chain_tip_epoch, chain_tip_hash),
        True,
        specific_peers=cfg.peers_activated
    )
    # print("~tip", chain_tip_epoch)


def fulfill_history_request(alias, query_id, chain_tip_epoch, chain_tip_hash):
    """send block history to requesting peer"""
    if chain_tip_epoch not in cfg.epochs:
        print("~no block from epoch", chain_tip_epoch)
        return

    if chain_tip_hash != cfg.hashes[chain_tip_epoch]:
        print("~block from alternate chain")
        return

    index = cfg.epochs.index(chain_tip_epoch) + 1
    history_epochs = cfg.epochs[index:]
    history_blocks = [cfg.blocks[epoch].convert_to_dict() for epoch in history_epochs]
    # print("~sent", history_blocks)
    cm.send_peer_message(alias, f"query_fulfillment|{query_id}|{history_blocks}")


def format_history_response(query, response):
    """format received string to list of dicts"""
    if response == "no_block":
        return response
    received_blocks = ast.literal_eval(response)
    if type(received_blocks) is list:
        for block in received_blocks:
            if type(block) is not dict:
                return
        return received_blocks


def conclude_history_process(process):
    #TODO!!!!MUST MAKE SURE THAT BLOCKS DONT GET ADDED MULTIPLE TIMES BY MULTIPLE PROCESSES!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    """incorporate information from history request"""
    # print("~3GOT HISTORY")
    # start = time.time()
    blocks = [bk.Block(init_dict=block) for block in process.cached_responses[0]]
    for block in blocks:
        if not block.check_block_valid():
            print("bad block")
            return
    for block in blocks[-cfg.DELAY :]:
        if (
            block.block_hash != cfg.temp_hashes[block.epoch_timestamp]
            or block.epoch_timestamp not in cfg.temp_hashes.keys()
        ):
            print("different chain")
            print(block.block_hash)
            print(cfg.temp_hashes[block.epoch_timestamp])
            print(block.epoch_timestamp)
            print(cfg.temp_hashes.keys())
            return
    
    cfg.staged_sync_blocks = blocks


