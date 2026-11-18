import copy
from chain.transaction import tx_id
from chain.utxo import apply_transaction
from chain.verifier import check_transaction, verify_transaction
from chain.wallet import build_transaction
from tests.helpers import A, B, C, D, E, GEN, GEN_ID, coin


def fresh():
    u = {}
    apply_transaction(u, GEN, GEN_ID)
    return u

def pay(vout, signers, outs):
    t, v, spk = coin(vout)
    return build_transaction([(t, v, spk, signers)], outs)


def test_valid_spend_moves_coins():
    u = fresh()
    tx = pay(0, [A], [(60, B.lock), (39, A.lock)])
    assert verify_transaction(tx, u)
    assert (GEN_ID, 0) not in u and (tx_id(tx), 0) in u and (tx_id(tx), 1) in u

def test_fee_is_returned():
    assert check_transaction(pay(0, [A], [(60, B.lock), (37, A.lock)]), fresh()) == (True, "ok", 3)

def test_double_spend_against_set():
    u = fresh()
    assert verify_transaction(pay(0, [A], [(99, B.lock)]), u)
    ok, reason, _ = check_transaction(pay(0, [A], [(99, C.lock)]), u)
    assert not ok and "already-spent" in reason

def test_same_coin_twice_in_one_tx():
    t, v, spk = coin(0)
    tx = build_transaction([(t, v, spk, [A]), (t, v, spk, [A])], [(150, B.lock)])
    ok, reason, _ = check_transaction(tx, fresh())
    assert not ok and "listed twice" in reason

def test_outputs_exceed_inputs():
    assert not check_transaction(pay(3, [D], [(101, D.lock)]), fresh())[0]

def test_negative_output_cannot_mint():
    # outputs 150 + (-60) = 90 <= 100 would pass a sum-only fee check
    tx = pay(0, [A], [(150, B.lock), (-60, A.lock)])
    assert not check_transaction(tx, fresh())[0]

def test_wrong_signer():
    assert not check_transaction(pay(1, [A], [(99, A.lock)]), fresh())[0]

def test_edit_after_signing_breaks_signature():
    tx = pay(0, [A], [(60, B.lock), (39, A.lock)])
    tx["outputs"][0]["value"] = 61
    ok, reason, _ = check_transaction(tx, fresh())
    assert not ok and "script" in reason

def test_vault_needs_two_distinct_keyholders():
    u = fresh()
    assert not check_transaction(pay(5, [A, A], [(99, D.lock)]), u)[0]
    assert verify_transaction(pay(5, [B, C], [(99, D.lock)]), u)

def test_multi_input_transaction():
    ta, va, sa = coin(0); tb, vb, sb = coin(1)
    tx = build_transaction([(ta, va, sa, [A]), (tb, vb, sb, [B])], [(198, E.lock)])
    assert verify_transaction(tx, fresh())

def test_failed_verification_leaves_set_unchanged():
    u = fresh(); before = copy.deepcopy(u)
    assert not verify_transaction(pay(0, [D], [(10, D.lock)]), u)
    assert u == before

def test_empty_inputs_or_outputs():
    assert not check_transaction({"inputs": [], "outputs": [{"value": 1, "script_pubkey": []}]}, fresh())[0]
    assert not check_transaction(pay(0, [A], []), fresh())[0]
