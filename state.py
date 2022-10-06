import config as cfg
import json
import os

class State:
    def __init__(self) -> None:
        self.epoch = 0
        self.bc_epochs = {}  # {epoch: alias}
        self.taken_nyms = set()
        self.nym_owners = {}  # {alias: nym}

    def duplicate(self):#this should probably override copy instead
        dup = State()
        dup.epoch = self.epoch
        dup.bc_epochs = self.bc_epochs
        dup.taken_nyms = list(self.taken_nyms)
        dup.nym_owners = self.nym_owners
        dup.write_to_disk()
        return dup


    def write_to_disk(self):
        output = {}
        output['epoch'] = self.epoch
        output['bc_epochs'] = {epoch:list(self.bc_epochs[epoch]) for epoch in self.bc_epochs}
        output['taken_nyms'] = list(self.taken_nyms)
        output['nym_owners'] = self.nym_owners

        dump = json.dumps(output)
        name = os.path.join(f"./{cfg.ALIAS}/states", f"{self.epoch}.json")
        with open(name, "wb") as f:
            f.write(dump.encode("utf-8"))

    def __del__(self):
        name = os.path.join(f"./{cfg.ALIAS}/states", f"{self.epoch}.json")
        os.remove(name)

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
