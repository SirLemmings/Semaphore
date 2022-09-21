# Author: Alex Dulisse
# Version: 0.4.1

# Packages included with python
import socket, json
import random
import time
import hashlib

# Imports from natively defined packages
from alias_management import get_claimed_aliases
from bidict import bidict

with open("params_test.json") as f:
    params = json.load(f)

# The standard length of an alias within the Semaphore network
ALIAS_LEN = params["ALIAS_LEN"]

# The standard length of a signature in a block
SIG_LEN = params["SIG_LEN"]

# The standard length of the chain commitments in the block
CHAIN_COMMIT_LEN = params["CHAIN_COMMIT_LEN"]

#
INDICATOR_LEN = params["INDICATOR_LEN"]

# The standard length of a message header
HEADER_LENGTH = params["HEADER_LENGTH"]

# The timebase offset used for testing time synchronicity
TIME_BASE_OFFSET = params["TIME_BASE_OFFSET"] #+ random.random() * 10

#
CLOCK_INTERVAL = params["CLOCK_INTERVAL"]

# The standard length of an epoch (in seconds)
EPOCH_TIME = params["EPOCH_TIME"]

# The number of posterior slack epochs used for message relay
SLACK_EPOCHS = params["SLACK_EPOCHS"]

# The number of prior slack epochs used for message relay
FORWARD_SLACK_EPOCHS = params["FORWARD_SLACK_EPOCHS"]

# The number of peers sampled for updating the node's time
TIME_SAMPLE_NUM = params["TIME_SAMPLE_NUM"]

# The alpha parameter used for the exponential smoothing update of the node's time
TIME_INERTIA = params["TIME_INERTIA"]

# The alloted time (in seconds) for a time update process before it is deleted
TIME_PROCESS_DURATION = params["TIME_PROCESS_DURATION"]

# The weight given to the node's local time when updating the node's network time
LOCAL_WEIGHT = params["LOCAL_WEIGHT"]

# The threshold of error for which the node will start reporting a corrected time
TIME_ERROR_THRESHOLD = params["TIME_ERROR_THRESHOLD"]

# The threshold of error beyond which a node will reject a peer's sampled time
REPORT_ERROR_THRESHOLD = params["REPORT_ERROR_THRESHOLD"]

# The correction factor used for adjusting the node's reported time
EXTRA_CORRECTION_DRIFT = params["EXTRA_CORRECTION_DRIFT"]

# 
SAFETY_FACTOR = params["SAFETY_FACTOR"]

# The initial voting confidence used for broadcasts that have already been seen
VOTE_INIT_CONF = params["VOTE_INIT_CONF"]

# The initial voting confidence used for broadcasts that have not already been seen
VOTE_INIT_CONF_NEG = params["VOTE_INIT_CONF_NEG"]

# The number of peers sampled during epoch voting
VOTE_SAMPLE_NUM = params["VOTE_SAMPLE_NUM"]

# 
VOTE_CONSENSUS_LEVEL = params["VOTE_CONSENSUS_LEVEL"]

#
VOTE_CERTAINTY_LEVEL = params["VOTE_CERTAINTY_LEVEL"]

# The maximum number of epochs that are used for epoch voting
VOTE_MAX_EPOCHS = params["VOTE_MAX_EPOCHS"]

# The alloted time (in seconds) for a round of voting before the process is deleted
VOTE_ROUND_TIME = params["VOTE_ROUND_TIME"]

# The number of epochs alloted for synching a new block after voting ends
SYNC_EPOCHS = params["SYNC_EPOCHS"]

# The minimum fork depth for the node to reorg to an alternate chain
MINIMUM_REORG_DEPTH = params["MINIMUM_REORG_DEPTH"]

# Enable manual broadcasting
ENABLE_MANUAL_BC = True

# Send test broadcasts to the network periodically
SEND_TEST_BC = True

# Add a random delay to the clock
RANDOM_DELAY = True

# Print relayed broadcasts
SHOW_RELAYS =True

# Print information for each new block
SHOW_BLOCK_INFO = True

# Print information for each new epoch
SHOW_EPOCH_INFO = True
SHOW_CONF_BC = False
SHOW_SEEN_BC = False
SHOW_VOTE_CONFS = False

# The total delay (in epochs) from when an epoch starts to when it is finalized
DELAY = SLACK_EPOCHS + VOTE_MAX_EPOCHS + FORWARD_SLACK_EPOCHS + SYNC_EPOCHS + 1

# The alias of the node
ALIAS = 0

# The IP (listening) address of the node
IP = socket.gethostbyname(socket.gethostname() + ".local")

# The listening port of the node
PORT = 0

# The public key associated with the node's alias
pk = 0

# The private/secret key associated with the node's alias
sk = 0

# Dictionary of all activated aliases and their public keys
alias_keys = get_claimed_aliases() # {alias: pk}

# Dictionary of all of the node's peers
peers = {} # {alias: peer object}

# Dictionary of all activated peers
peers_activated = {}

# All of the node's speaking sockets
all_speaking = {} # {alias: socket}

# All of the node's listening sockets
all_listening = {} # {alias: socket}

# The node's server socket where it listens for new connections
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# The offset between the network time and the node's local time
network_offset = 0

# If the node/network has been initialized
initialized = False

# The most recent finalized epoch
committed_epoch = float("inf")

# If the node is synced to the rest of the network
synced = False

# If the node is activated
activated = False

# The epoch that the node was activated in
activation_epoch = float("inf")

# Enforce the validity of the chain
enforce_chain = True

# number of epochs to offset before a block is finalized
chain_commit_offset = {}

# The current network epoch
current_epoch = 0

# All open epoch-related processes
epoch_processes = {} # {epoch: open process}

# All epochs that have been closed
finished_epoch_processes = set()

# The finalized block that is currently staged for addition to the history at the end of the epoch
staged_block_updates = []

# Dictionary of blocks that are being held before adding to the chain
temp_staged_block_updates = []

# If the node will automatically resync with the network upon reactivation
resync = False

# The epochs that each of the node's chain commitments belong to
epoch_chain_commit = bidict({})  # {chain_commit: epoch}

# The epoch of the genesis block
GENESIS = range(DELAY * 2 - 1)

# All blocks in existence thus far
blocks = {i * EPOCH_TIME: "GENESIS" for i in GENESIS}  # {epoch: block}
epochs = [i * EPOCH_TIME for i in GENESIS]
hashes = bidict({i * EPOCH_TIME: str(i) for i in GENESIS})  # {epoch: hash}
indexes = bidict({i * EPOCH_TIME: i for i in GENESIS})  # {epoch: index}


temp_blocks = {}
temp_epochs = []
temp_hashes = bidict({})
staged_sync_blocks = []


def network_time() -> float:
    """
    Retrieves the node's network time from the local time and network offset
    """ 
    return time.time() + network_offset


def chain_commitment(epoch: int, where=None) -> str:
    """
    Retrieves the chain commitments associated with the given epoch.

    This function will work for epochs in the past, present, and future
    as long as sufficient blocks were confirmed prior to the epoch
    and no epochs were skipped.

    Parameters:
        epoch (int): The epoch to find the chain commitment for
        where: UNIMPLEMENTED

    Returns:
        A string of the joined hashes of the commited epochs,
        padded with zeros to keep the same standard length.
    """
    # print(where)
    if synced:
        eps = epochs
        hs = hashes
    else:
        eps = temp_epochs
        hs = temp_hashes

    earliest_process_epoch = (
        current_epoch - (SLACK_EPOCHS + VOTE_MAX_EPOCHS + SYNC_EPOCHS) * EPOCH_TIME
    )
    last_commit_epoch = epoch - DELAY * EPOCH_TIME

    if epoch not in eps and epoch < earliest_process_epoch:
        print(epoch, earliest_process_epoch)
        raise Exception("skipped epoch")
    if last_commit_epoch > earliest_process_epoch:
        # print(epoch)
        # print(last_commit_epoch)
        # print(earliest_process_epoch)
        raise Exception("insufficient blocks confirmed")

    # if epoch in eps:
    #     print('a')
    #     epoch_index = eps.index(epoch)
    #     committed_epochs = eps[epoch_index - 2 * DELAY : epoch_index - DELAY]
    # print('~last',last_commit_epoch)
    # for ep in eps:
    #     print(ep)
    #     print(ep==last_commit_epoch)
    if last_commit_epoch in eps:
        # print("b")
        last_index = eps.index(last_commit_epoch)
        committed_epochs = eps[last_index - DELAY + 1 : last_index] + [
            last_commit_epoch
        ]
    else:
        # print("c")
        # offset = int((current_epoch - epoch) / EPOCH_TIME + FORWARD_SLACK_EPOCHS)
        if epoch in chain_commit_offset:
            offset = chain_commit_offset[epoch]
        else:
            offset = 0
        committed_epochs = eps[-DELAY - offset :]
        committed_epochs = committed_epochs[:DELAY]

    if len(committed_epochs) != DELAY:
        raise Exception(f"uh oh wrong nuber of epoch {epoch}")
    
    com_hashes = [hs[epoch] for epoch in committed_epochs]
    commitment = ""
    for com_hash in com_hashes:
        commitment += com_hash
    # print("~", hashlib.sha256(commitment.encode()).hexdigest(), commitment)
    if where == "ep":
        # print(committed_epochs)
        # print([epoch for epoch in committed_epochs])
        return (
            hashlib.sha256(commitment.encode()).hexdigest(),
            [epoch for epoch in committed_epochs],
        )
    # if where == 'ep':
    # print(hashlib.sha256(commitment.encode()).hexdigest(), commitment)

    return hashlib.sha256(commitment.encode()).hexdigest()

