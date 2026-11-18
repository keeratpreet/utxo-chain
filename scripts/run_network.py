"""
Run the multi-node network and report whether the nodes agree.

Starts one process per node, lets them mine and sync, stops mining a few
seconds before the end so the last blocks can spread, then validates every
node's chain from genesis and prints a summary.

    python scripts/run_network.py [--seconds 30] [--config config.json] [--data data]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chain.blockchain import cumulative_work, load_chain, replay
from chain.node import chain_file
from chain.transaction import tx_id
from scripts.make_pool import make_pool


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--quiet", type=float, default=5)
    args = ap.parse_args()
    cfg = json.load(open(args.config))

    shutil.rmtree(args.data, ignore_errors=True)
    os.makedirs(args.data)
    pool = make_pool(cfg["pool_size"], cfg["double_spend_every"], cfg["num_nodes"])
    json.dump(pool, open(os.path.join(args.data, "pool.json"), "w"), indent=1)
    print(f"pool: {len(pool['transactions'])} transactions, {len(pool['conflicts'])} double-spend pairs; "
          f"{cfg['num_nodes']} nodes, difficulty {cfg['difficulty']}, {args.seconds:.0f}s\n")

    procs = [subprocess.Popen([sys.executable, "-m", "chain.node", "--id", str(i), "--config", args.config,
                               "--data", args.data, "--seconds", str(args.seconds), "--quiet", str(args.quiet)],
                              cwd=ROOT) for i in range(cfg["num_nodes"])]
    for p in procs:
        p.wait()

    print("\n=== result ===")
    tips = set()
    for i in range(cfg["num_nodes"]):
        chain = load_chain(chain_file(args.data, i))
        replay(chain, cfg["block_reward"])  # raises if invalid
        tips.add(chain[-1].hash)
        ntx = sum(len(b.transactions) - 1 for b in chain[1:])
        print(f"node {i}: height {chain[-1].index}, tip {chain[-1].hash[:16]}, work {cumulative_work(chain)}, "
              f"{ntx} txs, valid from genesis")
    print(f"\nconverged: {'yes, all nodes hold the same chain' if len(tips) == 1 else 'NO'}")

    mined = {tx_id(t) for b in chain for t in b.transactions}
    for a, b in pool["conflicts"]:
        state = "both mined (BUG)" if a in mined and b in mined else "one mined" if a in mined or b in mined else "neither mined"
        print(f"double-spend pair {a[:8]} / {b[:8]}: {state}")
    left = len(pool["transactions"]) - len([t for t in pool["transactions"] if tx_id(t) in mined])
    print(f"{left} pool transactions not mined (the losing side of each double spend)")
    sys.exit(0 if len(tips) == 1 else 1)


if __name__ == "__main__":
    main()
