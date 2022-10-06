import config as cfg


class State:
    def __init__(self,save=True) -> None:
        self.epoch = 0
        self.bc_epochs = {}  # {epoch: alias}
        self.taken_nyms = set()
        self.nym_owners = {}  # {alias: nym}


buckets = []


def clear_state():
    if len(cfg.historic_epochs) > cfg.SAVED_STATES_NUM:
        history = cfg.historic_epochs[: -cfg.SAVED_STATES_NUM]
        last_epoch = history[-1]
        if last_epoch % cfg.SAVED_STATES_NUM != 0:
            del cfg.historic_sates[last_epoch]
            cfg.historic_epochs.remove(last_epoch)
        else:
            buckets.append([last_epoch])

            for i in range(len(buckets) - 2, 0, -1):
                if len(buckets[i - 1]) == len(buckets[i]) and len(buckets[i]) == len(
                    buckets[i + 1]
                ):
                    buckets[i - 1] += buckets.pop(i)
            saved_epochs = {b[0] for b in buckets}

            for epoch in history:
                if epoch not in saved_epochs:
                    cfg.historic_epochs.remove(epoch)
                    del cfg.historic_sates[epoch]
