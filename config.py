import socket, json
from alias_management import get_claimed_aliases
import hashlib
from bidict import bidict

with open("params.json") as f:
    params = json.load(f)
ALIAS_LEN = params["ALIAS_LEN"]
SIG_LEN = params["SIG_LEN"]
CHAIN_COMMIT_LEN = params["CHAIN_COMMIT_LEN"]
INDICATOR_LEN = params["INDICATOR_LEN"]
HEADER_LENGTH = params["HEADER_LENGTH"]
TIME_BASE_OFFSET = params["TIME_BASE_OFFSET"]
CLOCK_INTERVAL = params["CLOCK_INTERVAL"]
EPOCH_TIME = params["EPOCH_TIME"]
SLACK_EPOCHS = params["SLACK_EPOCHS"]
FORWARD_SLACK_EPOCHS = params["FORWARD_SLACK_EPOCHS"]
TIME_SAMPLE_NUM = params["TIME_SAMPLE_NUM"]
TIME_INERTIA = params["TIME_INERTIA"]
TIME_PROCESS_DURATION = params["TIME_PROCESS_DURATION"]
LOCAL_WEIGHT = params["LOCAL_WEIGHT"]
TIME_ERROR_THRESHOLD = params["TIME_ERROR_THRESHOLD"]
REPORT_ERROR_THRESHOLD = params["REPORT_ERROR_THRESHOLD"]
EXTRA_CORRECTION_DRIFT = params["EXTRA_CORRECTION_DRIFT"]
SAFETY_FACTOR = params["SAFETY_FACTOR"]
VOTE_INIT_CONF = params["VOTE_INIT_CONF"]
VOTE_INIT_CONF_NEG = params["VOTE_INIT_CONF_NEG"]
VOTE_SAMPLE_NUM = params["VOTE_SAMPLE_NUM"]
VOTE_CONSENSUS_LEVEL = params["VOTE_CONSENSUS_LEVEL"]
VOTE_CERTAINTY_LEVEL = params["VOTE_CERTAINTY_LEVEL"]
VOTE_MAX_EPOCHS = params["VOTE_MAX_EPOCHS"]
VOTE_ROUND_TIME = params["VOTE_ROUND_TIME"]
SYNC_EPOCHS = params["SYNC_EPOCHS"]
MINIMUM_REORG_DEPTH = params["MINIMUM_REORG_DEPTH"]

ENABLE_MANUAL_BC = True
SEND_TEST_BC = True
RANDOM_DELAY = False

SHOW_RELAYS = False
SHOW_BLOCK_INFO = True
SHOW_EPOCH_INFO = True
SHOW_CONF_BC = False
SHOW_SEEN_BC = True
SHOW_VOTE_CONFS = False

DELAY = SLACK_EPOCHS + VOTE_MAX_EPOCHS + FORWARD_SLACK_EPOCHS + SYNC_EPOCHS + 1

ALIAS = 0
IP = socket.gethostbyname(socket.gethostname() + ".local")
PORT = 0

pk = 0
sk = 0
alias_keys = get_claimed_aliases()

peers = {}
peers_activated = {}
all_speaking = {}
all_listening = {}

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
network_offset = 0

initialized = False
committed_epoch = float("inf")
synced = False
activated = False
activation_epoch = float("inf")
bootstrapped_epoch = float("inf")
enforce_chain = True
sync_blocks_staged = False
bootstrapping = False

chain_commit_offset = {}
current_epoch = 0
epoch_processes = {}
finished_epoch_processes = set()
staged_block_updates = []
temp_staged_block_updates = []


epoch_chain_commit = bidict({})  # {epoch:chain_commit}

GENESIS = range(DELAY)
blocks = {i * EPOCH_TIME: "GENESIS" for i in GENESIS}  # {epoch: block}
epochs = [i * EPOCH_TIME for i in GENESIS]
hashes = bidict({i * EPOCH_TIME: str(i) for i in GENESIS})  # {epoch: hash}
indexes = bidict({i * EPOCH_TIME: i for i in GENESIS})  # {epoch: index}


temp_blocks = {}
temp_epochs = []
temp_hashes = bidict({})
staged_sync_blocks = []


# def chain_commitment(epoch, where=None):
#     if synced:
#         eps = epochs
#         hs = hashes
#     else:
#         eps = temp_epochs
#         hs = temp_hashes

#     earliest_process_epoch = (
#         current_epoch - (SLACK_EPOCHS + VOTE_MAX_EPOCHS + SYNC_EPOCHS) * EPOCH_TIME
#     )
#     last_commit_epoch = epoch - DELAY * EPOCH_TIME

#     if epoch not in eps and epoch < earliest_process_epoch:
#         print(epoch, earliest_process_epoch)
#         raise Exception("skipped epoch")
#     if last_commit_epoch > earliest_process_epoch:
#         raise Exception("insufficient blocks confirmed")

#     if (
#         not bootstrapping
#     ):  # once synced a chain commitment is made even if there is no block
#         # eps = sorted(list(epoch_chain_commit.keys()))
#         eps = list(range(last_commit_epoch-EPOCH_TIME*DELAY*2, last_commit_epoch + EPOCH_TIME, EPOCH_TIME))#There are extra elements here 
#         last_index = eps.index(last_commit_epoch)
#         committed_epochs = eps[last_index - DELAY + 1 : last_index] + [
#             last_commit_epoch
#         ]

#     else:  # these may be redundant with above, but i dont want to break things rn
#         print(bootstrapping)
#         if last_commit_epoch in eps:
#             last_index = eps.index(last_commit_epoch)
#             committed_epochs = eps[last_index - DELAY + 1 : last_index] + [
#                 last_commit_epoch
#             ]
#             print(1)
#         else:
#             if epoch in chain_commit_offset:
#                 offset = chain_commit_offset[epoch]
#             else:
#                 offset = 0
#             committed_epochs = eps[-DELAY - offset :]
#             committed_epochs = committed_epochs[:DELAY]
#             print(2)

#     if len(committed_epochs) != DELAY:
#         raise Exception(f"uh oh wrong nuber of epoch {epoch}")

#     com_hashes = [hs[epoch] for epoch in committed_epochs]
#     # com_hashes = [
#     #     hs[epoch] if epoch in hs else epoch_chain_commit[epoch]
#     #     for epoch in committed_epochs
#     # ]
#     if where == "ep":
#         print([h[:6] for h in com_hashes])
#         # print([epoch_chain_commit[e][:6] for e in sorted(epoch_chain_commit)])
#         # print([hashes[h][:6] for h in sorted(hashes)])
#     commitment = ""
#     for com_hash in com_hashes:
#         commitment += com_hash
#     if where == "ep":
#         return (
#             hashlib.sha256(commitment.encode()).hexdigest(),
#             [epoch for epoch in committed_epochs],
#         )
#     return hashlib.sha256(commitment.encode()).hexdigest()

