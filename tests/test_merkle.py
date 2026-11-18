from chain.crypto import sha256_hex
from chain.merkle import merkle_proof, merkle_root, verify_proof

leaves = lambda n: [sha256_hex(f"tx{i}") for i in range(n)]

def test_empty_and_single():
    assert merkle_root([]) == sha256_hex("")
    assert merkle_root(leaves(1)) == leaves(1)[0]

def test_odd_level_duplicates_last():
    l = leaves(3)
    assert merkle_root(l) == sha256_hex(sha256_hex(l[0] + l[1]) + sha256_hex(l[2] + l[2]))

def test_every_leaf_proves_inclusion():
    for n in range(1, 12):
        l = leaves(n); root = merkle_root(l)
        for i in range(n):
            assert verify_proof(l[i], merkle_proof(l, i), root)

def test_edited_leaf_fails_proof():
    l = leaves(6); root = merkle_root(l)
    assert not verify_proof(sha256_hex("forged"), merkle_proof(l, 2), root)
