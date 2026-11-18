import time
from chain.node import Node
from scripts.make_pool import make_pool


def test_threaded_nodes_converge(tmp_path):
    cfg = {"num_nodes": 3, "difficulty": 3, "block_reward": 50, "max_transactions_per_block": 3,
           "sync_frequency_seconds": 0.3, "pool_size": 16, "double_spend_every": 5}
    pool = make_pool(cfg["pool_size"], cfg["double_spend_every"], cfg["num_nodes"])
    nodes = [Node(i, cfg, str(tmp_path), [pool["transactions"][j] for j in pool["orders"][i]]) for i in range(3)]
    for n in nodes:
        n.start()
    time.sleep(6)
    for n in nodes:
        n.mining_enabled = False
    time.sleep(2)
    for n in nodes:
        n.stop()
    for n in nodes:
        n.sync_once()
    tips = {n.chain.tip.hash for n in nodes}
    assert len(tips) == 1 and nodes[0].chain.tip.index > 1
    assert all(n.chain.validate_chain() for n in nodes)
    mined = {t for b in nodes[0].chain.chain for t in map(__import__("chain.transaction", fromlist=["tx_id"]).tx_id, b.transactions)}
    for a, b in pool["conflicts"]:
        assert not (a in mined and b in mined)
