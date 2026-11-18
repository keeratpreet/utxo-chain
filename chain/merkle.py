"""
Merkle trees over transaction ids.

Each level hashes the concatenated hex strings of a pair with SHA-256; an odd
node is paired with a copy of itself. merkle_proof / verify_proof let anyone
check that one transaction is in a block using only the header's root.
"""
from .crypto import sha256_hex


def _next_level(level: list[str]) -> list[str]:
    if len(level) % 2:
        level = level + [level[-1]]
    return [sha256_hex(level[i] + level[i + 1]) for i in range(0, len(level), 2)]


def merkle_root(leaves: list[str]) -> str:
    """Root of the tree whose leaves are `leaves` (hex txids). Empty list -> sha256("")."""
    if not leaves:
        return sha256_hex("")
    level = list(leaves)
    while len(level) > 1:
        level = _next_level(level)
    return level[0]


def merkle_proof(leaves: list[str], index: int) -> list[tuple[str, str]]:
    """Sibling hashes from leaf `index` up to the root, as (side, hash) with side 'L' or 'R'."""
    if not 0 <= index < len(leaves):
        raise IndexError(index)
    proof, level = [], list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level = level + [level[-1]]
        sib = index ^ 1
        proof.append(("L" if sib < index else "R", level[sib]))
        level = _next_level(level)
        index //= 2
    return proof


def verify_proof(leaf: str, proof: list[tuple[str, str]], root: str) -> bool:
    """Rebuild the root from a leaf and its proof and compare."""
    h = leaf
    for side, sib in proof:
        h = sha256_hex(sib + h) if side == "L" else sha256_hex(h + sib)
    return h == root
