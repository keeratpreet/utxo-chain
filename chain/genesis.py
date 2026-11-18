"""
The fixed genesis block every node starts from.

All fields are constants (including the timestamp), so every node computes
the same genesis hash. Its single transaction funds the demo wallets and a
2-of-3 multisig vault shared by alice, bob and carol.
"""
from .block import Block
from .merkle import merkle_root
from .transaction import make_coinbase, tx_id
from .wallet import Wallet, multisig_lock

GENESIS_TIMESTAMP = 1767225600  # 2026-01-01 00:00:00 UTC
WALLET_NAMES = ["alice", "bob", "carol", "dave", "erin"]
WALLETS = {name: Wallet(name) for name in WALLET_NAMES}
VAULT_SIGNERS = ["alice", "bob", "carol"]
VAULT_LOCK = multisig_lock(2, [WALLETS[n].pubkey for n in VAULT_SIGNERS])
ALLOCATION = 100


def genesis_transaction() -> dict:
    outputs = [{"value": ALLOCATION, "script_pubkey": WALLETS[n].lock} for n in WALLET_NAMES]
    outputs.append({"value": ALLOCATION, "script_pubkey": VAULT_LOCK})
    return make_coinbase(0, outputs)


def make_genesis_block() -> Block:
    txs = [genesis_transaction()]
    return Block(index=0, previous_hash="0", merkle_root=merkle_root([tx_id(t) for t in txs]),
                 nonce=0, timestamp=GENESIS_TIMESTAMP, difficulty=0, transactions=txs)
