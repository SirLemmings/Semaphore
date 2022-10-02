import ast
from cgi import test
import hashlib
import config as cfg
import communications as cm
import broadcasts as bc
import peers as pr
import blocks as bk
import sched, time
from process import Process
from threading import Thread


class VoteProcessor:
    """
    A class used to manage how epoch voting is conducted
    
    Attributes:
    """

    def __init__(self, epoch, seen_bc):
        """
        Creates a VoteManager object using the parent Node object

        Most parameters are loaded from the parameter file
        
        Parameters: 
            parent (Node): The node object using this vote manager
        """
        self.epoch = epoch
        self.execute = True
        self.broadcasts = {bc.calc_bcid(broadcast): broadcast for broadcast in seen_bc}
        if self.epoch >= cfg.activation_epoch:
            self.confs = {
                bc.calc_bcid(broadcast): cfg.VOTE_INIT_CONF for broadcast in seen_bc
            }
        else:
            self.confs = {bc.calc_bcid(broadcast): 0 for broadcast in seen_bc}
        self.count = 0
        self.vote_rounds = 0
        self.s = sched.scheduler(time.time, time.sleep)
        self.s.enter(0, 0, self.execute_vote)
        self.pending_commits = set()
        self.seen_commits = set()
        self.rejected_commits = set()
        self.rejected_bcids = set()
        self.rejected_peers = set()
        Thread(target=self.s.run, name=f"vote_{self.epoch}").start()

    def execute_vote(self):
        self.requested_commits_this_round = set()
        if self.execute:
            self.s.enter(cfg.VOTE_ROUND_TIME, 0, self.execute_vote)
            self.initiate_vote_update()

    def initiate_vote_update(self):
        """
        Initiates a round of voting.

        This function takes a random sample of known peers, opens a voting process,
        and sends vote requests to those peers

        Parameters:
            epoch (int): The epoch of broadcasts to be voted upon
        """
        Process(
            cfg.VOTE_SAMPLE_NUM,
            self.format_vote_response,
            self.conclude_vote_process,
            "vote_request",
            self.epoch,
            True,
            specific_peers=set(cfg.peers_activated.copy()) - self.rejected_peers,
        )

    def fulfill_vote_request(self, alias: int, request_id: str):
        """
        Fulfills a vote request from a peer for a given epoch

        Parameters:
            alias (int): A valid alias of the peer that sent the request
            request_id (str): The ID of the request that was received
            epoch (int): The epoch of broadcasts to vote on
        """
        if self.epoch >= cfg.activation_epoch:
            acks = {bcid for bcid in self.broadcasts if self.confs[bcid] > 0}
            if acks == set():
                acks = {}
            commit = cfg.epoch_chain_commit[self.epoch]
            cm.send_peer_message(
                alias, f"query_fulfillment|{request_id}|{[acks,commit]}",
            )

    def format_vote_response(self, query, response):
        """format recieved string to set"""
        response = ast.literal_eval(response)
        received_acks = response[0]
        commit = response[1]
        
        if cfg.synced and (cfg.activated or cfg.enforce_chain):
            if commit == cfg.epoch_chain_commit[self.epoch]:
                if received_acks == {}:
                    received_acks = set()
                if type(received_acks) is set:
                    return received_acks
            else:
                print('wrong commit')
                print(commit)
                print(cfg.epoch_chain_commit[self.epoch])
                return "wrong_commit"
        else:
            if received_acks == {}:
                received_acks = set()
            if type(received_acks) is set:
                return received_acks

        

    def conclude_vote_process(self, process):
        """incorporate information for round of epoch vote"""
        # TODO ***RIGHT NOW PEERS ARE REJECTED BY GIVING BROADCASTS FROM A DIFFERENT CHAIN. IT IS PROBABLY BEST IF ACKS THEMSELVES ARE REJECTED
        acks = [i for i in process.cached_responses if i != "wrong_commit"]
        self.epoch_vote(acks, process)

    def epoch_vote(self, acks, process):
        """
        Updates the confidences for broadcasts based on the votes received by peers

        Parameters:
            acks (list): The responses (votes) of the sampled peers
            vote_process_id (int): The ID of the voting process
        """
        if acks == []:
            return
        sufficient_samples = len(acks) >= cfg.VOTE_SAMPLE_NUM
        acks_union = set.union(*acks)
        acks_union = set.union(acks_union, self.broadcasts)

        peers_responded = process.peers_responded
        self.accomodate_missing_bc(acks_union, peers_responded)

        combined_acks = {bcid: 0 for bcid in acks_union}
        for peer_acks in acks:
            for bcid in peer_acks:
                combined_acks[bcid] += 1
        for bcid in combined_acks:
            if sufficient_samples:
                if combined_acks[bcid] >= cfg.VOTE_CONSENSUS_LEVEL:
                    self.confs[bcid] += 1
                elif (
                    combined_acks[bcid]
                    <= cfg.VOTE_SAMPLE_NUM - cfg.VOTE_CONSENSUS_LEVEL
                ):
                    self.confs[bcid] -= 1
            else:  # right now the sufficient samples case is just a special case of the below, but we may want to change the insuffcient case in the future
                if (
                    combined_acks[bcid]
                    >= len(acks) * cfg.VOTE_CONSENSUS_LEVEL / cfg.VOTE_SAMPLE_NUM
                ):
                    self.confs[bcid] += 1
                elif (
                    combined_acks[bcid]
                    <= cfg.VOTE_SAMPLE_NUM
                    - len(acks) * cfg.VOTE_CONSENSUS_LEVEL / cfg.VOTE_SAMPLE_NUM
                ):
                    self.confs[bcid] -= 1
        self.vote_rounds += 1

        # TODO CHECK FOR DRIFT
        if cfg.SHOW_VOTE_CONFS and self.epoch % (cfg.EPOCH_TIME * 2) == 0:
            for c in self.confs:
                print(f"{c}: {self.confs[c]}")
            print()

    def request_missing_broadcast(self, alias: int, bcid: str):
        """
        Requests the information of a broadcast that the peer knows but the node has not yet seen

        Parameters:
            alias (int): A valid alias of the peer to request the broadcast from
            bcid (str): The ID of the missing broadcast
            epoch (int): The epoch that the missing broadcast belongs to 
        """
        Process(
            1,
            VoteProcessor.format_bc_response,
            self.conclude_bc_process,
            "bc_request",
            (self.epoch, bcid),
            True,
            specific_peers=[alias],
        )

    def fulfill_bc_request(self, alias: int, query_id: str, bcid: str):
        """
        Fulfills the request from a peer for a specific broadcast

        Parameters:
            alias (int): A valid alias of the peer to send the broadcast to
            query_id (str): The ID of the related query
            bcid (str): The ID of the requested broadcast
            epoch (int): The epoch that the broadcast belongs to 
        """

        broadcast = self.broadcasts[bcid]
        cm.send_peer_message(alias, f"query_fulfillment|{query_id}|{[bcid,broadcast]}")

    @staticmethod
    def format_bc_response(query, response):
        """format recieved string to list"""
        response = ast.literal_eval(response)
        if type(response) is list:
            return response

    def conclude_bc_process(self, process):
        """incorporate data from missing bc request"""
        bcid, broadcast = process.cached_responses[0]
        alias = process.specific_peers[0]
        if bcid != bc.calc_bcid(broadcast):
            print("peer send broadcast that didn't match bcid")
            pr.remove_peer(alias)
            return
        if bcid in self.broadcasts:
            return
        if not bc.check_broadcast_validity_vote(broadcast, self.epoch):
            self.rejected_bcids.add(bcid)
            return
        commit = bc.split_broadcast(broadcast)["chain_commit"]
        if cfg.synced:
            if commit == cfg.epoch_chain_commit[self.epoch]:
                self.broadcasts[bcid] = broadcast
            else:
                print("REJECTED")
                print(commit)
                print(cfg.epoch_chain_commit[self.epoch])
                self.rejected_bcids.add(bcid)
                self.rejected_peers.add(alias)
            # Check it is on your commit
        elif cfg.enforce_chain:
            if commit[:64] in self.seen_commits:
                self.broadcasts[bcid] = broadcast
            elif commit[:64] in self.rejected_commits:
                self.rejected_bcids.add(bcid)
            elif commit[:64] not in self.requested_commits_this_round:
                self.request_history(alias)
                self.pending_commits.add(commit[:64])
                self.requested_commits_this_round.add(commit[:64])
        else:
            self.broadcasts[bcid] = broadcast

    def request_history(self, alias):
        chain_tip_epoch = cfg.epochs[-1]
        chain_tip_hash = cfg.hashes[chain_tip_epoch]

        Process(
            1,
            VoteProcessor.format_history_response,
            self.conclude_history_process,
            "history_request",
            (chain_tip_epoch, chain_tip_hash),
            True,
            specific_peers=[alias],
        )

    @staticmethod
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

    def conclude_history_process(self, process):
        if process.cached_responses[0] == "no_block":
            alias = list(process.peers_responded.keys())[0]
            self.rejected_peers.add(alias)
            return
        blocks = [bk.Block(init_dict=block) for block in process.cached_responses[0]]
        for block in blocks:
            if not block.check_block_valid():
                print("bad block")
                return
        block_hashes = []
        test_count = 0
        for block in blocks:
            test_count += 1
            block_hashes.append(block.block_hash)
            commitment = ""
            if len(block_hashes) >= cfg.DELAY:
                for block_hash in block_hashes[-cfg.DELAY :]:
                    commitment += block_hash
                commitment = hashlib.sha256(commitment.encode()).hexdigest()

                if commitment in self.pending_commits:
                    self.seen_commits.add(commitment)
                    return
        if test_count > 0:
            self.rejected_commits.add(commitment)
            alias = list(process.peers_responded.keys())[0]
            self.rejected_peers.add(alias)

    def terminate_vote(self):
        """
        Terminates the voting process for the specific epoch

        Parameters:
            epoch (int): The epoch of broadcasts that was voted on
        """
        # print('~final bc',self.broadcasts)
        if self.execute:
            self.execute = False
            return [self.broadcasts[bc] for bc in self.broadcasts if self.confs[bc] > 0]
        return None

    def accomodate_missing_bc(self, acks_union, peers_responeded):
        """
        Updates the set of unconfirmed broadcasts (and confidences) based on differences in the sets of seen broadcasts

        Parameters:
            acks_union (set): The union of the sets of seen broadcasts across the node and its peers
            epoch (int): The epoch that is being voted on (and that the broadcasts belong to)
            acks_individual (list):
            peers_responded (list): The peers that responded in the voting round

        """
        for bcid in acks_union:
            if bcid not in self.broadcasts and bcid not in self.rejected_bcids:
                self.confs[bcid] = cfg.VOTE_INIT_CONF_NEG - self.vote_rounds - 1
                for alias in peers_responeded:
                    if bcid in peers_responeded[alias]:
                        self.request_missing_broadcast(alias, bcid)

