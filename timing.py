import connections as cn
import config as cfg
import sched
import time
import clock as cl
import communications as cm
import consensus as cs
from epoch_processor import EpochProcessor
from bidict import bidict

FREQ = int(cfg.EPOCH_TIME / cfg.CLOCK_INTERVAL)
position = 0
aligned = False


def time_events():
    """
    Executes actions on ticks of the clock, including at start of epoch
    
    The event loop runs continuously on its own thread managing time synchronization, epoch tracking, and . 
    """

    s = sched.scheduler(time.time, time.sleep)

    def event_loop():
        """functions that execute on a timer with epochs"""
        global position
        global aligned
        now = cfg.network_time()
        cl.initiate_time_update()

        if aligned:
            offset = now - cfg.current_epoch + position * cfg.CLOCK_INTERVAL
        else:
            offset = now % cfg.CLOCK_INTERVAL
        s.enter((cfg.CLOCK_INTERVAL - offset), 0, event_loop)

        if not aligned and round(now, 2) % cfg.EPOCH_TIME == 0:
            aligned = True
        if aligned:
            if position == 0:
                run_epoch()
            position += 1
            position %= FREQ

    s.enter(0, 0, event_loop)
    s.run()


def run_epoch():
    next_epoch = cfg.current_epoch + cfg.FORWARD_SLACK_EPOCHS * cfg.EPOCH_TIME
    
    # global prev
    # try:
    #     print("~elpased", time.time() - prev)
    # except:
    #     pass
    # prev = time.time()
    if cfg.SHOW_EPOCH_INFO:
        print()
        print()
        print()
        print("~EPOCH", cfg.current_epoch)
        print(len(cfg.staged_sync_blocks))
        # print("~CHAIN_COMMIT_LEN", len(cfg.epoch_chain_commit))
    # print((cfg.epoch_chain_commit.keys()))
    # print((cfg.epoch_chain_commit.values()))
    # print(cfg.epochs)
    # print(cfg.chain_commit_offset)
    # print("~comit", len(cfg.epoch_chain_commit))
    # print("~comit", sorted(cfg.epoch_chain_commit.keys()))
    # print()
    if cfg.initialized:
        try:
            for epoch in cfg.epoch_processes:
                cfg.epoch_processes[epoch].step()

            if (
                next_epoch not in cfg.epoch_processes
            ):  # TODO do something better than this check
                start_epoch_process(next_epoch)
        except RuntimeError as e:
            print("IGNORING ERROR:")
            print(e)
        

        if cfg.current_epoch > 0:

            if cfg.SEND_TEST_BC and cfg.activated and len(cfg.epoch_processes) > 1:
                for i in range(1):
                    # cm.originate_broadcast(f"{cfg.ALIAS}{i}{cfg.network_time()}")
                    cm.originate_broadcast("test")

            for epoch in cfg.finished_epoch_processes:
                try:
                    cfg.epoch_processes[epoch].kill_process()
                except KeyError as e:
                    print('IGNORING ERROR:')
                    print(e)
            cfg.finished_epoch_processes = set()

            cs.load_staged_updates()

            if len(cfg.staged_sync_blocks) > 0:
                # print("~4MORE THAN 0")
                cs.sync_func(cfg.staged_sync_blocks)

        if cfg.committed_epoch == float("inf"):
            if len(cfg.temp_epochs) == cfg.DELAY:
                cfg.committed_epoch = cfg.current_epoch + cfg.EPOCH_TIME
        elif (
            not cfg.synced
            # and len(cfg.temp_epochs) == cfg.DELAY * 2
            # not cfg.synced and len(cfg.epoch_chain_commit) == cfg.DELAY
        ):  # TODO this is delayed by cfg.DELAY periods because the chain commit might be borked if it is run not at the start of epoch process. should fix the function and remove the extra delay
            # print("~1SYNC!!!!!!!!!!!!!!!!!!")
            cs.sync()

        # elif cfg.resync:
        #     InitSyncProcessor()
        #     cfg.resync=False

    if cfg.current_epoch == 0:
        cfg.current_epoch = round(cfg.network_time()) + cfg.EPOCH_TIME
    else:
        cfg.current_epoch += cfg.EPOCH_TIME
        if cfg.current_epoch != round(cfg.network_time()) + cfg.EPOCH_TIME:
            pass
            # print(
            #     f"~WARNING TIMES NOT MATCH {cfg.current_epoch} {round(cfg.network_time()) + cfg.EPOCH_TIME}"
            # )


# TODO remove this function once we know its working. just merge with run_epoch
def start_epoch_process(epoch=cfg.current_epoch):
    """initiate new epoch process"""
    # print("running")
    if epoch in cfg.epoch_processes:
        print("something went very wrong. epoch process already exists")
    cfg.epoch_processes[epoch] = EpochProcessor(epoch)


def initialize():
    print("EPOCH PROCESSING ACTIVATED")
    # PAST = cfg.SYNC_EPOCHS + cfg.VOTE_MAX_EPOCHS + cfg.SLACK_EPOCHS
    # FUTURE = cfg.FORWARD_SLACK_EPOCHS + 1
    # activating_epochs = range(
    #     cfg.current_epoch - PAST * cfg.EPOCH_TIME,
    #     cfg.current_epoch + FUTURE * cfg.EPOCH_TIME,
    #     cfg.EPOCH_TIME,
    # )
    # for epoch in activating_epochs:
    #     start_epoch_process(epoch)

    cfg.initialized = True


def deactivate():
    print("EPOCH PROCESSING HALTED")
    cn.signal_deactivation()
    processor_epochs = [epoch for epoch in cfg.epoch_processes.keys()]
    for epoch in processor_epochs:
        try:
            cfg.epoch_processes[epoch].kill_process()
        except:
            pass

    cfg.initialized = False
    cfg.committed_epoch = float("inf")
    cfg.synced = False
    cfg.activated = False
    cfg.enforce_chain = False
    cfg.activation_epoch = float("inf")

    cfg.temp_blocks = {}
    cfg.temp_epochs = []
    cfg.temp_hashes = bidict({})
    cfg.staged_sync_blocks = []

    cfg.staged_block_updates = []
    cfg.temp_staged_block_updates = []
    cfg.staged_sync_blocks = []

    cfg.finished_epoch_processes = set()
