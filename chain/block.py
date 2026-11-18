"""
Block: a header (index, previous_hash, merkle_root, nonce, timestamp,
difficulty) and a body of UTXO transactions.

The block hash is SHA-256 over the header fields. The transactions are bound
to the header through the Merkle root of their txids.
"""
from .crypto import sha256_hex
from .merkle import merkle_root
from .transaction import tx_id


class Block:
    def __init__(self, index, previous_hash, merkle_root, nonce, timestamp, difficulty, transactions, hash_value=None):
        self.index = index
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.nonce = nonce
        self.timestamp = timestamp
        self.difficulty = difficulty
        self.transactions = transactions
        self.hash = hash_value or self.calculate_hash()

    def header_string(self) -> str:
        return f"{self.index}|{self.previous_hash}|{self.merkle_root}|{self.nonce}|{self.timestamp}|{self.difficulty}"

    def calculate_hash(self) -> str:
        return sha256_hex(self.header_string())

    def txids(self) -> list[str]:
        return [tx_id(tx) for tx in self.transactions]

    def compute_merkle_root(self) -> str:
        return merkle_root(self.txids())

    def meets_difficulty(self) -> bool:
        return self.hash.startswith("0" * self.difficulty)

    @property
    def work(self) -> int:
        """Work credited to this block: 2^difficulty."""
        return 2 ** self.difficulty

    def to_dict(self) -> dict:
        return {
            "index": self.index, "previous_hash": self.previous_hash, "merkle_root": self.merkle_root,
            "nonce": self.nonce, "timestamp": self.timestamp, "difficulty": self.difficulty,
            "transactions": self.transactions, "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(d["index"], d["previous_hash"], d["merkle_root"], d["nonce"], d["timestamp"],
                   d["difficulty"], d["transactions"], hash_value=d["hash"])
