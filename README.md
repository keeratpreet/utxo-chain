# UTXO Chain

A multi-node blockchain in Python that combines two course assignments (SIL7163, Prof. Subodh V. Sharma):

- **Blockchain Fundamentals (A1):** blocks, SHA-256 block hashing, Merkle trees, Proof-of-Work mining, and consensus across nodes by cumulative work.
- **UTXO Transaction Verifier (A2):** UTXO set, canonical transaction serialization, a stack-based Bitcoin Script interpreter, and ECDSA (secp256k1) signatures.

In A1, block bodies held account-style transfers that the mining node signed for everyone. Here, blocks carry real UTXO transactions signed by the coin owners. Every block is checked by replaying its transactions through the script verifier against the coins that exist at that point in the chain.

## What it does

| Area | Implementation |
|---|---|
| Nodes | Each node is its own process with a mining thread and a sync thread. A node publishes its chain as a file, and peers read it. |
| Proof of Work | A nonce search until `sha256(index\|previous_hash\|merkle_root\|nonce\|timestamp\|difficulty)` starts with `difficulty` zero hex digits. Mining stops as soon as the node's tip changes. |
| Fork choice | Adopt the valid chain with the most cumulative work, Σ 2^difficulty. On a tie, the chain whose last block has the smaller hash wins, so every node breaks the tie the same way. |
| Chain validation | Replays from a fixed genesis block. Every block must have the right index, a matching `previous_hash` link, a correct stored hash, enough PoW, a matching Merkle root, a coinbase no larger than reward + fees, and only valid transactions. |
| Merkle trees | Pairs of txids hashed with SHA-256, the last node duplicated on odd levels. Includes inclusion proofs (`merkle_proof`) and their verification (`verify_proof`). |
| Transactions | UTXO inputs and outputs. The txid is `hash256` of canonical JSON. Inputs are signed with deterministic, low-S ECDSA over secp256k1. |
| Script | `OP_DUP`, `OP_HASH160`, `OP_EQUAL`, `OP_EQUALVERIFY`, `OP_VERIFY`, `OP_CHECKSIG`, `OP_CHECKMULTISIG`. Supports P2PKH and m-of-n multisig. |
| Verification | Rejects transactions with no inputs or no outputs, the same coin listed twice, missing or already-spent coins, scripts that fail, non-positive outputs, or outputs above inputs. On success the UTXO set changes atomically. |

## Layout

```
chain/
  crypto.py       SHA-256 / hash160 / hash256, ECDSA sign and verify
  merkle.py       Merkle root, inclusion proofs, proof verification
  script.py       stack-based script interpreter
  transaction.py  canonical serialization, txid, signing message, coinbase
  utxo.py         UTXO set operations
  verifier.py     transaction rules (check_transaction / verify_transaction)
  wallet.py       deterministic wallets, P2PKH / multisig locks, transaction signing
  block.py        block header, hash, PoW check, work
  genesis.py      fixed genesis block funding the demo wallets and a 2-of-3 vault
  blockchain.py   chain replay and validation, mining, fork choice, sync, persistence
  node.py         one node process: mining and sync threads
scripts/
  make_pool.py    signed transaction pool with deliberate double-spend pairs
  run_network.py  start N node processes, then check they converged
tests/            37 tests: script, verifier, Merkle, chain, consensus, threaded network
```

## Run

```bash
pip install -r requirements.txt
python -m pytest -q                        # 37 tests
python scripts/run_network.py --seconds 45
```

`run_network.py` creates a pool of 40 signed payments (P2PKH and vault spends, some with two inputs). It adds 5 double-spend pairs, where each pair spends the same coins twice. Each node gets the pool in a different order, so nodes mine different blocks and forks happen. A sample run with 4 nodes at difficulty 5:

```
node 0: adopted peer chain: tip 2 000005c6b602, work 65, rolled back 2 of its own block(s)
node 3: adopted peer chain: tip 6 00000d3faa50, work 193, rolled back 1 of its own block(s)
node 0: adopted peer chain: tip 8 00000c8777d1, work 257, rolled back 3 of its own block(s)
...
node 0: height 8, tip 00000c8777d1e2ab, work 257, 40 txs, valid from genesis
node 1: height 8, tip 00000c8777d1e2ab, work 257, 40 txs, valid from genesis
node 2: height 8, tip 00000c8777d1e2ab, work 257, 40 txs, valid from genesis
node 3: height 8, tip 00000c8777d1e2ab, work 257, 40 txs, valid from genesis
converged: yes, all nodes hold the same chain
double-spend pair d303b0e0 / 3421042e: one mined     (x5)
5 pool transactions not mined (the losing side of each double spend)
```

Settings are in `config.json`: `num_nodes`, `difficulty`, `block_reward`, `max_transactions_per_block`, `sync_frequency_seconds`, `pool_size`, `double_spend_every`.

## Design notes

- **Signing message.** For input *i*, every input's `script_sig` is emptied and input *i*'s is replaced by the locking script of the coin it spends. A2 kept the other inputs' signatures in the message, so a transaction with two inputs could never be signed. Emptying them, as Bitcoin's SIGHASH_ALL does, fixes this.
- **Deterministic genesis.** A1 created genesis with the current time, so each node had a different genesis hash. Here genesis is all constants.
- **Work = 2^difficulty**, as in A1. With difficulty counted in hex digits, the expected number of hashes is 16^d. Both measures rank chains with equal difficulties the same way.
- **Peer transport** is files, as in the A1 framework, not sockets. Swapping in sockets would only change `Node.peers` and `sync_once`.
- **Fixes over the original assignments:** `OP_CHECKMULTISIG` no longer counts one key twice (two copies of Alice's signature used to satisfy a 2-of-3 lock). Outputs must be positive integers, because a negative output could offset a larger one. Transaction selection now picks up a child listed before its parent in the pool.
