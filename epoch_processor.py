# Author: Alex Dulisse
# Version: 0.4.1

from relay_processor import RelayProcessor
from vote_processor import VoteProcessor
from build_processor import BuildProcessor
import config as cfg
import connections as cn

EPOCH_VOTE_DELAY = (cfg.FORWARD_SLACK_EPOCHS + cfg.SLACK_EPOCHS) * cfg.EPOCH_TIME
BUILD_DELAY = (
    cfg.VOTE_MAX_EPOCHS + cfg.SLACK_EPOCHS + cfg.FORWARD_SLACK_EPOCHS
) * cfg.EPOCH_TIME
FINALIZE_DELAY = (
    cfg.SYNC_EPOCHS + cfg.VOTE_MAX_EPOCHS + cfg.SLACK_EPOCHS + cfg.FORWARD_SLACK_EPOCHS
) * cfg.EPOCH_TIME


class EpochProcessor:
    """
    This class handles the processing of everything for a particular epoch.
    and makes a child processor for each stage of epoch processing
    """

    def __init__(self, epoch):
        self.epoch = epoch
        self.cached_processes = []
        self.staged_cached_processes = []
        self.processor = RelayProcessor(self.epoch)
        self.state = "relay"
        self.time_alive = 0

        # if self.epoch >= cfg.activation_epoch:
        if epoch >= cfg.committed_epoch:
            # print('process',self.epoch,cfg.chain_commitment(self.epoch, "ep"))
            # print(self.epoch)
            # print(cfg.chain_commitment(self.epoch, where="ep")[0])
            cfg.epoch_chain_commit[self.epoch], self.test = cfg.chain_commitment(
                self.epoch, where="ep"
            )
            # print('~true', self.epoch, cfg.epoch_chain_commit[self.epoch])

    def step(self) -> None:
        """
        Update processor at the end of each epoch
        """

        # try:
        #     print(
        #         cfg.chain_commitment(
        #             self.epoch,
        #             where="ep"
        #         )[1]
        #     )
        #     print(self.test)
        # except:
        #     print('-')

        # print()

        self.time_alive += cfg.EPOCH_TIME
        if self.time_alive == FINALIZE_DELAY:
            # print("~done delay", self.epoch)

            self.processor.finalize_block()
            cfg.finished_epoch_processes.add(self.epoch)
            if self.epoch == cfg.activation_epoch - cfg.EPOCH_TIME:
                cn.signal_activation()
                cfg.activated = True
                cfg.enforce_chain = True
                print("***ACTIVATED***")
        elif self.time_alive == BUILD_DELAY:
            # print("~sync delay", self.epoch)
            confirmed_bc = self.processor.terminate_vote()
            # print('~done terminate')
            self.processor = BuildProcessor(self.epoch, confirmed_bc)
            self.state = "sync"
        elif self.time_alive == EPOCH_VOTE_DELAY:
            # print("~vote delay", self.epoch)
            seen_bc = self.processor.seen_bc    
            # print("~seen bc:",len(seen_bc))
            self.processor = VoteProcessor(self.epoch, seen_bc)
            self.state = "vote"
        self.cached_processes = self.staged_cached_processes.copy()
        self.staged_cached_processes = []
        self.execute_cached_processes()

    def kill_process(self) -> None:
        """
        Kills the process object
        """
        if self.state == "vote":
            self.processor.execute = False
        self.processor = None
        del cfg.epoch_processes[self.epoch]

    # def delete_reference(self):
    #     """remove from memory"""
    #     cfg.finished_epoch_processes.add(self.epoch)

    def execute_new_process(self, state, func, *args) -> None:
        """
        Respond to a message from a peer. if it should be processed next epoch then it is cached
        """
        if state == self.state:
            func = self.find_func(func)
            func(*args)
        else:
            self.staged_cached_processes.append(
                {"state": state, "func": func, "args": args}
            )

    def execute_cached_processes(self) -> None:
        """
        Execute all valid processes, delete otherwise
        """
        for process in self.cached_processes:
            state = process["state"]
            func = process["func"]
            args = process["args"]
            if state == self.state:
                func = self.find_func(func)
                func(*args)

    def find_func(self, func) -> function:
        """
        Given the type of process return the correct function of child processor
        """
        if func == "block_request":
            func = self.processor.fulfill_block_request
        if func == "relay":
            func = self.processor.handle_relay
        if func == "bc_request":
            func = self.processor.fulfill_bc_request
        if func == "vote_request":
            func = self.processor.fulfill_vote_request
        return func
