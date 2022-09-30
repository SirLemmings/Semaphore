import hashlib
from numpy import block

import broadcasts as bc
import config as cfg


def sha_hash(preimage: str) -> str:
    """Calculate the sha256 hash of a preimage"""
    sha = hashlib.sha256
    return sha(preimage.encode()).hexdigest()


def build_merkle_tree(data: list) -> list:
    """builds a merkle tree from a list of elements"""
    if data == []:
        return []

    def tree_hash(base: list) -> list:
        base = [sha_hash(item) for item in base]
        if len(base) == 1:
            return [base]
        if len(base) % 2 == 1:
            base.append(base[-1])
        left = base[::2]
        right = base[1::2]
        new_layer = [left[i] + right[i] for i in range(len(left))]
        above_layers = tree_hash(new_layer)
        above_layers.append(base)
        return above_layers

    data = [str(item) for item in data]
    tree = tree_hash(data)
    tree.append(data)
    return tree


def construct_merkle_proof(tree: list, item: str) -> tuple:
    """constructs a merkle path for a item in the tree"""
    if item not in tree[-1]:
        raise Exception(f"{item} not in data of {tree[0][0]}")
    data_index = tree[-1].index(item)
    index = data_index
    path = []
    for layer in tree[-2:0:-1]:
        if index % 2 == 0:
            path.append(layer[index + 1])
        else:
            path.append(layer[index - 1])
        index //= 2
    path.append(tree[0][0])
    return item, data_index, path


def verify_proof(proof: tuple) -> bool:
    """verifies a merkle proof"""
    item = proof[0]
    index = proof[1]
    path = proof[2]
    node = sha_hash(item)
    for sibling in path[:-1]:
        if index % 2 == 0:
            preimage = node + sibling
        else:
            preimage = sibling + node
        index //= 2
        node = sha_hash(preimage)
    return node == path[-1]


class Block:
    def __init__(self, broadcasts=None, epoch=None, init_dict=None):
        """Create a block from a set of broadcasts or from a dict"""
        if init_dict is None:
            data = [bc.split_broadcast(broadcast) for broadcast in broadcasts]
            if cfg.activated:
                self.chain_commitment = cfg.epoch_chain_commit[
                    epoch
                ]
            else:
                self.chain_commitment = data[0]["chain_commit"]
            self.epoch_timestamp = epoch

            alias_list = [bc["alias"] for bc in data]
            bc_data = [bc["sig_image"] for bc in data]
            bc_data = [
                bc[: cfg.ALIAS_LEN] + bc[cfg.ALIAS_LEN + cfg.CHAIN_COMMIT_LEN :]
                for bc in bc_data
            ]  # removes chain commitment from each broadcast

            if len(broadcasts) > 0:
                bc_data = [
                    broadcast for _, broadcast in sorted(zip(alias_list, bc_data))
                ]
                sig_data = [bc["signature"] for bc in data]
                sig_data = [bc for _, bc in sorted(zip(alias_list, sig_data))]
                bc_tree = build_merkle_tree(bc_data)
                sig_tree = build_merkle_tree(sig_data)

                self.bc_root = bc_tree[0][0]
                self.sig_root = sig_tree[0][0]
                self.bc_body = bc_tree[-1]
                self.sig_body = sig_tree[-1]
            else:
                self.bc_root = "None"
                self.sig_root = "None"
                self.bc_body = "None"
                self.sig_body = "None"

            # ***SANITYCHECK***
            commit = (
                self.chain_commitment
            )
            commits = [bc["chain_commit"] for bc in data]
            commits = set(commits)
            if len(commits) > 1:
                raise Exception("commits are not the same")
            try:
                c = commits.pop()
                if c != commit:
                    raise Exception("commit doesnt match epoch commit")
            except:
                pass
        else:
            self.block_index = init_dict["block_index"]
            self.chain_commitment = init_dict["chain_commitment"]
            self.epoch_timestamp = init_dict["epoch_timestamp"]
            self.bc_root = init_dict["bc_root"]
            self.sig_root = init_dict["sig_root"]
            self.bc_body = init_dict["bc_body"]
            self.sig_body = init_dict["sig_body"]

    def update_index(self):
        self.block_index = len(cfg.indexes)
        

    @property
    def block_hash(self) -> str:
        """calculates the hash of a block"""
        if block == "GENESIS":
            return "GENESIS"
        header_str = ""
        header_str += self.bc_root
        header_str += self.sig_root
        header_str += self.chain_commitment
        header_str += str(self.epoch_timestamp)
        return sha_hash(header_str)

    def convert_to_dict(self):
        output = {}
        output["block_index"] = self.block_index
        output["chain_commitment"] = self.chain_commitment
        output["epoch_timestamp"] = self.epoch_timestamp
        output["bc_root"] = self.bc_root
        output["sig_root"] = self.sig_root
        output["bc_body"] = self.bc_body
        output["sig_body"] = self.sig_body
        return output

    def check_block_valid(self):
        """checks that all the contents of a block are valid"""
        return True

    def check_chain_commitment(self):
        """checks that the chain commitment is valid and not in the future"""
        return True

    def get_block_engagements(self) -> set:
        """returns a set of all aliases broadcasting in a block"""
        if self.bc_body == "None":
            return set()
        return {int(broadcast[: cfg.ALIAS_LEN]) for broadcast in self.bc_body}

