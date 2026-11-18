"""
The chain: validation, mining and fork choice.

Validation replays every block from genesis and rebuilds the UTXO set, so a
chain is accepted only if every header is correct (hash, link, PoW, Merkle
root) and every transaction is valid against the coins that exist at that
point. Fork choice picks the valid chain with the most cumulative work
(sum of 2^difficulty); on a tie the chain whose last block has the smaller
hash wins, so every node resolves the tie the same way.
"""
import json
import os
import time

from .block import Block
from .genesis import make_genesis_block
from .merkle import merkle_root
from .transaction import is_coinbase, make_coinbase, tx_id
from .utxo import apply_transaction
from .verifier import check_transaction


class InvalidChain(Exception):
    pass


def check_header(block: Block, prev: Block, min_difficulty: int = 1) -> None:
    if block.index != prev.index + 1:
        raise InvalidChain(f"block {block.index}: index does not follow {prev.index}")
    if block.previous_hash != prev.hash:
        raise InvalidChain(f"block {block.index}: previous_hash does not match block {prev.index}")
    if block.hash != block.calculate_hash():
        raise InvalidChain(f"block {block.index}: stored hash is not the hash of its header")
    if block.difficulty < min_difficulty or not block.meets_difficulty():
        raise InvalidChain(f"block {block.index}: proof of work does not meet difficulty {block.difficulty}")
    if block.merkle_root != block.compute_merkle_root():
        raise InvalidChain(f"block {block.index}: Merkle root does not match its transactions")


def apply_block(block: Block, utxo: dict, reward: int | None) -> int:
    """Check and apply a block's transactions to `utxo`. Returns the fees collected."""
    txs = block.transactions
    if not txs or not is_coinbase(txs[0]) or txs[0]["coinbase"] != block.index:
        raise InvalidChain(f"block {block.index}: first transaction must be its coinbase")
    fees = 0
    for tx in txs[1:]:
        ok, reason, fee = check_transaction(tx, utxo)
        if not ok:
            raise InvalidChain(f"block {block.index}: {reason}")
        apply_transaction(utxo, tx, tx_id(tx))
        fees += fee
    coinbase = txs[0]
    outs = coinbase["outputs"]
    if not outs or not all(type(o.get("value")) is int and o["value"] > 0 and isinstance(o.get("script_pubkey"), list) for o in outs):
        raise InvalidChain(f"block {block.index}: malformed coinbase")
    if reward is not None and sum(o["value"] for o in outs) > reward + fees:
        raise InvalidChain(f"block {block.index}: coinbase pays more than reward + fees")
    apply_transaction(utxo, coinbase, tx_id(coinbase))
    return fees


def replay(chain: list[Block], reward: int, min_difficulty: int = 1) -> dict:
    """Validate a whole chain from genesis and return its UTXO set."""
    if not chain or chain[0].to_dict() != make_genesis_block().to_dict():
        raise InvalidChain("genesis block does not match")
    utxo: dict = {}
    apply_block(chain[0], utxo, None)
    for i in range(1, len(chain)):
        check_header(chain[i], chain[i - 1], min_difficulty)
        apply_block(chain[i], utxo, reward)
    return utxo


def cumulative_work(chain: list[Block]) -> int:
    return sum(b.work for b in chain)


def better(work_a: int, tip_a: str, work_b: int, tip_b: str) -> bool:
    """True if chain A beats chain B: more work, or equal work and a smaller tip hash."""
    return work_a > work_b or (work_a == work_b and tip_a < tip_b)


def proof_of_work(block: Block, should_stop=None, check_every: int = 20000) -> bool:
    """Search nonces until the hash has `difficulty` leading zeros. False if stopped."""
    prefix = "0" * block.difficulty
    while True:
        block.hash = block.calculate_hash()
        if block.hash.startswith(prefix):
            return True
        block.nonce += 1
        if should_stop and block.nonce % check_every == 0 and should_stop():
            return False


class Blockchain:
    def __init__(self, reward: int = 50, min_difficulty: int = 1):
        self.reward = reward
        self.min_difficulty = min_difficulty
        self.chain = [make_genesis_block()]
        self.utxo = replay(self.chain, reward, min_difficulty)

    @property
    def tip(self) -> Block:
        return self.chain[-1]

    def work(self) -> int:
        return cumulative_work(self.chain)

    def validate_chain(self, chain: list[Block] | None = None) -> bool:
        try:
            replay(chain if chain is not None else self.chain, self.reward, self.min_difficulty)
            return True
        except InvalidChain:
            return False

    # ---------- mining
    def select_transactions(self, pool: list[dict], max_txs: int) -> tuple[list[dict], int]:
        """
        FIFO over the pool, keeping each transaction that is valid on top of
        the ones already picked. Passes repeat while they add something, so a
        child listed before its parent still gets in once the parent is picked.
        """
        view = dict(self.utxo)
        picked, fees, taken = [], 0, set()
        progress = True
        while progress and len(picked) < max_txs:
            progress = False
            for i, tx in enumerate(pool):
                if len(picked) >= max_txs:
                    break
                if i in taken:
                    continue
                ok, _, fee = check_transaction(tx, view)
                if ok:
                    apply_transaction(view, tx, tx_id(tx))
                    picked.append(tx)
                    taken.add(i)
                    fees += fee
                    progress = True
        return picked, fees

    def build_candidate(self, pool: list[dict], max_txs: int, miner_lock: list, difficulty: int,
                        timestamp: int | None = None) -> Block | None:
        """Next block on the current tip, before proof of work. None if nothing is valid to include."""
        txs, fees = self.select_transactions(pool, max_txs)
        if not txs:
            return None
        index = self.tip.index + 1
        coinbase = make_coinbase(index, [{"value": self.reward + fees, "script_pubkey": miner_lock}])
        body = [coinbase, *txs]
        return Block(index=index, previous_hash=self.tip.hash, merkle_root=merkle_root([tx_id(t) for t in body]),
                     nonce=0, timestamp=int(time.time()) if timestamp is None else timestamp,
                     difficulty=difficulty, transactions=body)

    def mine_block(self, pool: list[dict], max_txs: int, miner_lock: list, difficulty: int) -> Block | None:
        block = self.build_candidate(pool, max_txs, miner_lock, difficulty)
        if block is None:
            return None
        proof_of_work(block)
        return block if self.add_block(block) else None

    def add_block(self, block: Block) -> bool:
        """Append a block that extends the current tip, if it is valid."""
        try:
            check_header(block, self.tip, self.min_difficulty)
            utxo = dict(self.utxo)
            apply_block(block, utxo, self.reward)
        except InvalidChain:
            return False
        self.chain.append(block)
        self.utxo = utxo
        return True

    # ---------- consensus
    def consider(self, chain: list[Block]) -> bool:
        """Adopt `chain` if it is valid and beats ours. Returns True if adopted."""
        if not better(cumulative_work(chain), chain[-1].hash, self.work(), self.tip.hash):
            return False
        try:
            utxo = replay(chain, self.reward, self.min_difficulty)
        except InvalidChain:
            return False
        self.chain, self.utxo = chain, utxo
        return True

    def sync_with_peer_logs(self, peer_files: list[str]) -> bool:
        """Read every peer's chain file and adopt the best valid chain."""
        changed = False
        for path in peer_files:
            chain = load_chain(path)
            if chain and self.consider(chain):
                changed = True
        return changed

    # ---------- persistence
    def save_to_file(self, path: str, node_id: str = "") -> None:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"node_id": node_id, "chain": [b.to_dict() for b in self.chain]}, f, indent=1)
        os.replace(tmp, path)

    def load_from_file(self, path: str) -> bool:
        chain = load_chain(path)
        if chain is None:
            return False
        try:
            utxo = replay(chain, self.reward, self.min_difficulty)
        except InvalidChain:
            return False
        self.chain, self.utxo = chain, utxo
        return True


def load_chain(path: str) -> list[Block] | None:
    """Read a chain file; None if it is missing or unreadable (e.g. mid-write)."""
    try:
        with open(path) as f:
            return [Block.from_dict(d) for d in json.load(f)["chain"]]
    except (OSError, ValueError, KeyError, TypeError):
        return None
