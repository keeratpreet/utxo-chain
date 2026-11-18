"""
Stack-based script interpreter modelled on Bitcoin Script.

script_sig runs first, then script_pubkey, on one shared stack. The script
succeeds only if exactly one true item is left. Any stack underflow, bad
data or unknown opcode fails immediately.

Elements are opcodes ("OP_..."), hex strings (signatures, public keys,
hashes) or small ints (m and n for multisig).
"""
from .crypto import hash160, verify_signature

OPCODES = {
    "OP_DUP", "OP_HASH160", "OP_EQUAL", "OP_EQUALVERIFY",
    "OP_VERIFY", "OP_CHECKSIG", "OP_CHECKMULTISIG",
}


def _truthy(x) -> bool:
    return x != 0 if isinstance(x, int) else bool(x)


def execute_script(script_sig: list, script_pubkey: list, message: bytes) -> bool:
    if not isinstance(script_sig, list) or not isinstance(script_pubkey, list):
        return False
    stack = []
    for item in script_sig + script_pubkey:
        if not (isinstance(item, str) and item.startswith("OP_")):
            # data: push it
            if isinstance(item, bool):
                return False
            if isinstance(item, int):
                stack.append(item)
            elif isinstance(item, str):
                if item.isdigit():
                    stack.append(int(item))
                else:
                    try:
                        stack.append(bytes.fromhex(item))
                    except ValueError:
                        return False
            else:
                return False
            continue

        if item == "OP_DUP":
            if len(stack) < 1:
                return False
            stack.append(stack[-1])

        elif item == "OP_HASH160":
            if len(stack) < 1 or not isinstance(stack[-1], bytes):
                return False
            stack.append(hash160(stack.pop()))

        elif item == "OP_EQUAL":
            if len(stack) < 2:
                return False
            stack.append(1 if stack.pop() == stack.pop() else 0)

        elif item == "OP_EQUALVERIFY":
            if len(stack) < 2:
                return False
            if stack.pop() != stack.pop():
                return False

        elif item == "OP_VERIFY":
            if len(stack) < 1 or not _truthy(stack.pop()):
                return False

        elif item == "OP_CHECKSIG":
            # stack: [..., sig, pubkey]
            if len(stack) < 2:
                return False
            pubkey, sig = stack.pop(), stack.pop()
            if not isinstance(pubkey, bytes) or not isinstance(sig, bytes):
                return False
            stack.append(1 if verify_signature(pubkey, message, sig) else 0)

        elif item == "OP_CHECKMULTISIG":
            # stack (top first): n, pubkey_n..pubkey_1, m, sig_m..sig_1
            if len(stack) < 1:
                return False
            n = stack.pop()
            if not isinstance(n, int) or n < 0 or len(stack) < n:
                return False
            pubkeys = [stack.pop() for _ in range(n)]
            if len(stack) < 1:
                return False
            m = stack.pop()
            if not isinstance(m, int) or m < 0 or m > n or len(stack) < m:
                return False
            sigs = [stack.pop() for _ in range(m)]
            # every signature must match a different key: a key is used up
            # once it has matched, so one signer cannot count twice
            used = [False] * n
            valid = 0
            for sig in sigs:
                for k, pk in enumerate(pubkeys):
                    if not used[k] and isinstance(pk, bytes) and isinstance(sig, bytes) \
                            and verify_signature(pk, message, sig):
                        used[k] = True
                        valid += 1
                        break
            stack.append(1 if valid >= m else 0)

        else:
            return False

    return len(stack) == 1 and _truthy(stack[0])
