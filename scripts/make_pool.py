"""
Generate a pool of signed UTXO transactions for the network demo.

Starting from the genesis coins, it builds a sequence of valid payments
(P2PKH and 2-of-3 vault spends, some with two inputs), so later transactions
spend the outputs of earlier ones. Every `double_spend_every`-th payment gets
a twin that spends the same coins to someone else: both are valid on their
own, but only one can ever be mined. Each node receives the pool in a
different order, so nodes build different blocks and forks happen.

    python scripts/make_pool.py [--config config.json] [--out data/pool.json]
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chain.genesis import VAULT_LOCK, VAULT_SIGNERS, WALLET_NAMES, WALLETS, genesis_transaction
from chain.transaction import tx_id
from chain.utxo import apply_transaction
from chain.verifier import check_transaction
from chain.wallet import build_transaction

OWNERS = WALLET_NAMES + ["vault"]


def lock_of(owner: str) -> list:
    return VAULT_LOCK if owner == "vault" else WALLETS[owner].lock


def owner_of(spk: list) -> str:
    if spk == VAULT_LOCK:
        return "vault"
    return next(n for n in WALLET_NAMES if WALLETS[n].lock == spk)


def signers_for(owner: str, rng: random.Random) -> list:
    if owner == "vault":
        return [WALLETS[n] for n in rng.sample(VAULT_SIGNERS, 2)]
    return [WALLETS[owner]]


def make_pool(size: int, double_every: int, num_orders: int, seed: int = 7) -> dict:
    rng = random.Random(seed)
    view: dict = {}
    g = genesis_transaction()
    apply_transaction(view, g, tx_id(g))
    txs, conflicts = [], []

    def payment(payer, coins, receiver):
        total = sum(view[c]["value"] for c in coins)
        fee = rng.randint(1, 3)
        amount = rng.randint(1, max(1, total - fee - 1))
        outs = [(amount, lock_of(receiver))]
        if total - amount - fee > 0:
            outs.append((total - amount - fee, lock_of(payer)))
        ins = [(t, v, view[(t, v)]["script_pubkey"], signers_for(payer, rng)) for t, v in coins]
        return build_transaction(ins, outs)

    view_before = {}  # txid -> UTXO view just before that payment, for building twins
    while len(txs) < size:
        by_owner: dict = {}
        for key, c in view.items():
            if c["value"] >= 5:
                by_owner.setdefault(owner_of(c["script_pubkey"]), []).append(key)
        payer = rng.choice(sorted(by_owner))
        coins = rng.sample(by_owner[payer], min(len(by_owner[payer]), rng.choice([1, 1, 2])))
        receiver = rng.choice([o for o in OWNERS if o != payer])
        tx = payment(payer, coins, receiver)
        ok, reason, _ = check_transaction(tx, view)
        assert ok, reason
        view_before[tx_id(tx)] = (dict(view), payer, coins, receiver)
        apply_transaction(view, tx, tx_id(tx))
        txs.append(tx)

    # twins only for payments whose outputs nothing else spends, so whichever
    # side of a double spend loses, no other transaction is stranded
    spent_parents = {inp["txid"] for t in txs for inp in t["inputs"]}
    leaves = [t for t in txs if tx_id(t) not in spent_parents]
    for tx in rng.sample(leaves, min(len(leaves), size // double_every if double_every else 0)):
        snapshot, payer, coins, receiver = view_before[tx_id(tx)]
        saved, view = view, snapshot
        twin = payment(payer, coins, rng.choice([o for o in OWNERS if o not in (payer, receiver)]))
        assert check_transaction(twin, view)[0]
        view = saved
        txs.append(twin)
        conflicts.append([tx_id(tx), tx_id(twin)])

    orders = []
    for _ in range(num_orders):
        order = list(range(len(txs)))
        rng.shuffle(order)
        orders.append(order)
    return {"transactions": txs, "orders": orders, "conflicts": conflicts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default="data/pool.json")
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    pool = make_pool(cfg["pool_size"], cfg["double_spend_every"], cfg["num_nodes"])
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(pool, open(args.out, "w"), indent=1)
    print(f"wrote {len(pool['transactions'])} transactions ({len(pool['conflicts'])} double-spend pairs) to {args.out}")


if __name__ == "__main__":
    main()
