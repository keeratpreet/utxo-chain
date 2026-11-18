import copy, json, os
from chain.block import Block
from chain.blockchain import Blockchain, InvalidChain, better, cumulative_work, proof_of_work, replay
from chain.genesis import make_genesis_block
from chain.merkle import merkle_root
from chain.transaction import make_coinbase, tx_id
from chain.wallet import Wallet, build_transaction
from tests.helpers import A, B, C, D, coin

M = Wallet("miner-test")
DIFF = 2


def spend(vout, signers, outs):
    t, v, spk = coin(vout)
    return build_transaction([(t, v, spk, signers)], outs)

def mined(chain, pool, d=DIFF):
    b = chain.mine_block(pool, 10, M.lock, d)
    assert b is not None
    return b

def block_on(prev, txs, d=DIFF, reward=50, fees=0, ts=1):
    body = [make_coinbase(prev.index + 1, [{"value": reward + fees, "script_pubkey": M.lock}]), *txs]
    b = Block(prev.index + 1, prev.hash, merkle_root([tx_id(t) for t in body]), 0, ts, d, body)
    proof_of_work(b)
    return b


def test_genesis_is_identical_everywhere():
    assert make_genesis_block().hash == make_genesis_block().hash == Blockchain().tip.hash

def test_mining_builds_a_valid_chain():
    c = Blockchain()
    b = mined(c, [spend(0, [A], [(60, B.lock), (39, A.lock)])])
    assert b.hash.startswith("0" * DIFF) and c.validate_chain()
    assert c.utxo[(tx_id(b.transactions[0]), 0)]["value"] == 51  # reward + fee

def test_tampered_transaction_in_old_block_is_detected():
    c = Blockchain()
    mined(c, [spend(0, [A], [(60, B.lock), (39, A.lock)])])
    mined(c, [spend(3, [D], [(99, C.lock)])])
    bad = copy.deepcopy(c.chain)
    bad[1].transactions[1]["outputs"][0]["value"] = 70
    try:
        replay(bad, 50); assert False
    except InvalidChain as e:
        assert "Merkle" in str(e)

def test_tampered_header_breaks_links():
    c = Blockchain()
    mined(c, [spend(0, [A], [(99, B.lock)])]); mined(c, [spend(3, [D], [(99, C.lock)])])
    bad = copy.deepcopy(c.chain)
    bad[1].nonce += 1; bad[1].hash = bad[1].calculate_hash()
    assert not c.validate_chain(bad)

def test_double_spend_across_blocks_rejected():
    c = Blockchain()
    mined(c, [spend(0, [A], [(99, B.lock)])])
    twin = spend(0, [A], [(99, C.lock)])
    assert c.mine_block([twin], 10, M.lock, DIFF) is None          # never selected
    assert not c.add_block(block_on(c.tip, [twin], fees=1))       # and rejected if forced in

def test_coinbase_cannot_overpay():
    c = Blockchain()
    assert not c.add_block(block_on(c.tip, [spend(0, [A], [(99, B.lock)])], fees=5))

def test_dependent_transactions_in_one_block():
    c = Blockchain()
    t1 = spend(0, [A], [(99, B.lock)])
    t2 = build_transaction([(tx_id(t1), 0, B.lock, [B])], [(98, C.lock)])
    b = mined(c, [t2, t1])   # t2 is skipped until t1 is in the view, then picked
    assert [tx_id(t) for t in b.transactions[1:]] == [tx_id(t1), tx_id(t2)]

def test_fork_choice_more_work_wins_even_if_shorter():
    g = make_genesis_block()
    long = [g]; long.append(block_on(long[-1], [], d=2)); long.append(block_on(long[-1], [], d=2))
    heavy = [g, block_on(g, [], d=4)]
    # an empty block body is just the coinbase; patch txs requirement by validating headers only
    assert cumulative_work(heavy) > cumulative_work(long)
    assert better(cumulative_work(heavy), heavy[-1].hash, cumulative_work(long), long[-1].hash)

def test_tie_goes_to_smaller_tip_hash():
    assert better(10, "0001", 10, "0002") and not better(10, "0002", 10, "0001")

def test_sync_adopts_heavier_valid_peer_and_ignores_invalid(tmp_path):
    mine, peer, liar = Blockchain(), Blockchain(), Blockchain()
    mined(mine, [spend(0, [A], [(99, B.lock)])])
    mined(peer, [spend(3, [D], [(99, C.lock)])], d=3)
    mined(liar, [spend(1, [B], [(99, A.lock)])], d=5)
    liar.chain[1].transactions[1]["outputs"][0]["value"] = 99999   # heavier but invalid
    for name, ch in [("peer", peer), ("liar", liar)]:
        ch.save_to_file(str(tmp_path / f"{name}.json"))
    assert mine.sync_with_peer_logs([str(tmp_path / "liar.json"), str(tmp_path / "peer.json")])
    assert mine.tip.hash == peer.tip.hash

def test_tie_resolves_identically_on_both_nodes(tmp_path):
    n1, n2 = Blockchain(), Blockchain()
    mined(n1, [spend(0, [A], [(99, B.lock)])]); mined(n2, [spend(0, [A], [(99, C.lock)])])
    assert n1.work() == n2.work() and n1.tip.hash != n2.tip.hash
    n1.save_to_file(str(tmp_path / "1.json")); n2.save_to_file(str(tmp_path / "2.json"))
    n1.sync_with_peer_logs([str(tmp_path / "2.json")]); n2.sync_with_peer_logs([str(tmp_path / "1.json")])
    assert n1.tip.hash == n2.tip.hash == min(n1.tip.hash, n2.tip.hash)
