"""
Hashing and ECDSA (secp256k1) helpers.

sha256_hex is the hash used for blocks and Merkle trees (from the blockchain
assignment); hash256 / hash160 are the Bitcoin-style hashes used for
transaction ids and P2PKH locks (from the UTXO assignment).
"""
import hashlib

from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import sigdecode_string, sigencode_string_canonize


def sha256_hex(data) -> str:
    """SHA-256 of a str or bytes, as lowercase hex."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def ripemd160(data: bytes) -> bytes:
    try:
        h = hashlib.new("ripemd160")
    except ValueError:  # OpenSSL builds without RIPEMD160
        from Crypto.Hash import RIPEMD160
        h = RIPEMD160.new()
    h.update(data)
    return h.digest()


def hash160(data: bytes) -> bytes:
    """RIPEMD160(SHA256(data)), 20 bytes."""
    return ripemd160(hashlib.sha256(data).digest())


def hash256(data: bytes) -> bytes:
    """SHA256(SHA256(data)), 32 bytes."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def key_from_seed(seed: str) -> SigningKey:
    """Deterministic private key, so every node and test derives the same wallets."""
    return SigningKey.from_string(hashlib.sha256(seed.encode()).digest(), curve=SECP256k1)


def public_key_bytes(sk: SigningKey) -> bytes:
    """33-byte compressed public key."""
    return sk.get_verifying_key().to_string("compressed")


def sign(sk: SigningKey, digest: bytes) -> bytes:
    """ECDSA-sign a 32-byte digest. Deterministic (RFC 6979), low-S, raw 64-byte (r, s)."""
    return sk.sign_digest_deterministic(digest, hashfunc=hashlib.sha256, sigencode=sigencode_string_canonize)


def verify_signature(pubkey: bytes, message: bytes, signature: bytes) -> bool:
    """True iff `signature` is a valid ECDSA signature of `message` under `pubkey`."""
    try:
        vk = VerifyingKey.from_string(pubkey, curve=SECP256k1)
        return vk.verify_digest(signature, message, sigdecode=sigdecode_string)
    except Exception:
        return False
