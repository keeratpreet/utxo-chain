from chain.genesis import VAULT_LOCK, WALLETS, genesis_transaction
from chain.transaction import tx_id

GEN = genesis_transaction()
GEN_ID = tx_id(GEN)
# genesis outputs: 0 alice, 1 bob, 2 carol, 3 dave, 4 erin, 5 vault (2-of-3 alice/bob/carol)
A, B, C, D, E = (WALLETS[n] for n in ["alice", "bob", "carol", "dave", "erin"])


def coin(vout):
    return GEN_ID, vout, GEN["outputs"][vout]["script_pubkey"]
