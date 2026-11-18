"""
Transactions: canonical serialization, ids and signing messages.

A transaction is a dict:
    {"inputs":  [{"txid": hex, "vout": int, "script_sig": [...]}, ...],
     "outputs": [{"value": int, "script_pubkey": [...]}, ...]}
A coinbase transaction has no inputs and a "coinbase" field holding the block
index, which keeps every coinbase txid unique.
"""
import copy
import json

from .crypto import hash256


def canonical_serialize(tx: dict) -> bytes:
    """Sorted keys at every level, list order kept, no spaces, UTF-8."""
    return json.dumps(tx, sort_keys=True, separators=(",", ":")).encode("utf-8")


def tx_id(tx: dict) -> str:
    return hash256(canonical_serialize(tx)).hex()


def signing_message(tx: dict, input_index: int, spent_script_pubkey: list) -> bytes:
    """
    The 32-byte digest signed for input `input_index`.

    Every input's script_sig is emptied and this input's is replaced by the
    locking script of the coin it spends. Emptying the other inputs (as
    Bitcoin's SIGHASH_ALL does) means each input can be signed on its own, so
    one transaction can spend coins from several inputs.
    """
    t = copy.deepcopy(tx)
    for inp in t["inputs"]:
        inp["script_sig"] = []
    t["inputs"][input_index]["script_sig"] = spent_script_pubkey
    return hash256(canonical_serialize(t))


def is_coinbase(tx: dict) -> bool:
    return "coinbase" in tx and tx.get("inputs") == []


def make_coinbase(block_index: int, outputs: list[dict]) -> dict:
    return {"coinbase": block_index, "inputs": [], "outputs": outputs}
