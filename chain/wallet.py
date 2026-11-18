"""
Wallets: deterministic keys, locking scripts and ECDSA transaction signing.
"""
from .crypto import hash160, key_from_seed, public_key_bytes, sign
from .transaction import signing_message


class Wallet:
    def __init__(self, name: str):
        self.name = name
        self.key = key_from_seed(f"utxo-chain/{name}")
        self.pubkey = public_key_bytes(self.key)

    @property
    def lock(self) -> list:
        """P2PKH locking script for this wallet."""
        return p2pkh_lock(self.pubkey)

    def sign(self, digest: bytes) -> str:
        return sign(self.key, digest).hex()


def p2pkh_lock(pubkey: bytes) -> list:
    return ["OP_DUP", "OP_HASH160", hash160(pubkey).hex(), "OP_EQUALVERIFY", "OP_CHECKSIG"]


def multisig_lock(m: int, pubkeys: list[bytes]) -> list:
    return [m, *[p.hex() for p in pubkeys], len(pubkeys), "OP_CHECKMULTISIG"]


def build_transaction(inputs: list[tuple[str, int, list, list]], outputs: list[tuple[int, list]]) -> dict:
    """
    Build and sign a transaction.

    inputs:  (txid, vout, spent_script_pubkey, signers) where signers is a list
             of Wallets: one for P2PKH, m of them for an m-of-n multisig.
    outputs: (value, script_pubkey)
    """
    tx = {
        "inputs": [{"txid": t, "vout": v, "script_sig": []} for t, v, _, _ in inputs],
        "outputs": [{"value": val, "script_pubkey": spk} for val, spk in outputs],
    }
    for idx, (_, _, spk, signers) in enumerate(inputs):
        digest = signing_message(tx, idx, spk)
        if spk and spk[-1] == "OP_CHECKMULTISIG":
            tx["inputs"][idx]["script_sig"] = [w.sign(digest) for w in signers]
        else:
            w = signers[0]
            tx["inputs"][idx]["script_sig"] = [w.sign(digest), w.pubkey.hex()]
    return tx
