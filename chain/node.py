"""
One blockchain node, run as its own process.

A node mines on its own copy of the chain and shares it by writing its chain
file; a sync thread reads every peer's file and adopts the best valid chain.
Mining is interrupted as soon as the tip changes under it, so a node does not
keep working on a block that has already lost.

    python -m chain.node --id 0 --config config.json --data data
"""
import argparse
import json
import os
import threading
import time

from .blockchain import Blockchain, proof_of_work
from .wallet import Wallet


def chain_file(data_dir: str, node_id: int) -> str:
    return os.path.join(data_dir, f"node_{node_id}.json")


class Node:
    def __init__(self, node_id: int, config: dict, data_dir: str, pool: list[dict]):
        self.id = node_id
        self.cfg = config
        self.data_dir = data_dir
        self.pool = pool
        self.wallet = Wallet(f"miner-{node_id}")
        self.chain = Blockchain(reward=config["block_reward"])
        self.file = chain_file(data_dir, node_id)
        self.chain.load_from_file(self.file)
        self.lock = threading.Lock()
        self.running = False
        self.mining_enabled = True
        self.log_path = os.path.join(data_dir, f"node_{node_id}.log")

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] node {self.id}: {msg}"
        print(line, flush=True)
        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    def peers(self) -> list[str]:
        return [chain_file(self.data_dir, i) for i in range(self.cfg["num_nodes"]) if i != self.id]

    def save(self) -> None:
        self.chain.save_to_file(self.file, f"node_{self.id}")

    # ---------- threads
    def mine_once(self) -> bool:
        with self.lock:
            block = self.chain.build_candidate(self.pool, self.cfg["max_transactions_per_block"],
                                               self.wallet.lock, self.cfg["difficulty"])
            tip = self.chain.tip.hash
        if block is None:
            return False
        stop = lambda: not self.running or self.chain.tip.hash != tip
        if not proof_of_work(block, should_stop=stop):
            return False
        with self.lock:
            if self.chain.tip.hash == tip and self.chain.add_block(block):
                self.save()
                self.log(f"mined block {block.index} {block.hash[:12]} with {len(block.transactions) - 1} txs "
                         f"(nonce {block.nonce}, total work {self.chain.work()})")
                return True
        return False

    def mining_loop(self) -> None:
        while self.running:
            if not (self.mining_enabled and self.mine_once()):
                time.sleep(0.2)

    def sync_once(self) -> None:
        with self.lock:
            before = list(self.chain.chain)
            if self.chain.sync_with_peer_logs(self.peers()):
                self.save()
                new = self.chain.tip
                # our blocks that are no longer on the adopted chain
                kept = {b.hash for b in self.chain.chain}
                dropped = sum(1 for blk in before if blk.hash not in kept)
                self.log(f"adopted peer chain: tip {new.index} {new.hash[:12]}, work {self.chain.work()}"
                         + (f", rolled back {dropped} of its own block(s)" if dropped else ""))

    def sync_loop(self) -> None:
        while self.running:
            time.sleep(self.cfg["sync_frequency_seconds"])
            try:
                self.sync_once()
            except Exception as e:  # a bad peer file must not kill the node
                self.log(f"sync error: {e}")

    def start(self) -> None:
        self.running = True
        self.save()
        self.threads = [threading.Thread(target=self.mining_loop, daemon=True),
                        threading.Thread(target=self.sync_loop, daemon=True)]
        for t in self.threads:
            t.start()

    def stop(self) -> None:
        self.running = False
        for t in self.threads:
            t.join(timeout=5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--data", default="data")
    ap.add_argument("--seconds", type=float, default=30, help="total run time")
    ap.add_argument("--quiet", type=float, default=5, help="stop mining this long before the end so nodes converge")
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    pool = json.load(open(os.path.join(args.data, "pool.json")))
    order = pool["orders"][args.id % len(pool["orders"])]
    node = Node(args.id, cfg, args.data, [pool["transactions"][i] for i in order])
    node.log(f"start: {len(order)} txs in its pool, difficulty {cfg['difficulty']}")
    node.start()
    time.sleep(max(0, args.seconds - args.quiet))
    node.mining_enabled = False
    time.sleep(args.quiet)
    node.stop()
    node.sync_once()
    node.log(f"stop: tip {node.chain.tip.index} {node.chain.tip.hash[:12]}, work {node.chain.work()}")


if __name__ == "__main__":
    main()
