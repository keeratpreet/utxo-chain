import hashlib
from chain.crypto import key_from_seed, public_key_bytes, sign
from chain.script import execute_script
from chain.wallet import multisig_lock, p2pkh_lock
from tests.helpers import A, B, C, D

MSG = hashlib.sha256(b"message").digest()
sig = lambda w, m=MSG: w.sign(m)


def test_p2pkh_owner_unlocks():
    assert execute_script([sig(A), A.pubkey.hex()], A.lock, MSG)

def test_p2pkh_wrong_pubkey_fails_equalverify():
    assert not execute_script([sig(D), D.pubkey.hex()], A.lock, MSG)

def test_p2pkh_forged_signature_fails_checksig():
    assert not execute_script([sig(D), A.pubkey.hex()], A.lock, MSG)

def test_signature_bound_to_message():
    assert not execute_script([sig(A, hashlib.sha256(b"other").digest()), A.pubkey.hex()], A.lock, MSG)

LOCK = multisig_lock(2, [A.pubkey, B.pubkey, C.pubkey])

def test_multisig_two_different_signers():
    assert execute_script([sig(A), sig(C)], LOCK, MSG)

def test_multisig_same_signer_twice_rejected():
    # regression: one keyholder's signature repeated used to satisfy 2-of-3
    assert not execute_script([sig(A), sig(A)], LOCK, MSG)

def test_multisig_outsider_rejected():
    assert not execute_script([sig(A), sig(D)], LOCK, MSG)

def test_underflow_and_unknown_opcode():
    assert not execute_script([], ["OP_DUP"], MSG)
    assert not execute_script([1], ["OP_NOP"], MSG)
    assert not execute_script(["zz"], [], MSG)

def test_final_stack_must_be_single_true():
    assert not execute_script([1, 1], [], MSG)
    assert not execute_script([0], [], MSG)
    assert execute_script([1], [], MSG)
