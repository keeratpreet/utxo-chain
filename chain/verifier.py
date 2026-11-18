"""
Transaction verification against a UTXO set.

check_transaction runs every rule and reports why a transaction fails.
verify_transaction keeps the original interface: validate, and only if every
rule passes, update the UTXO set atomically.
"""
from .script import execute_script
from .transaction import is_coinbase, signing_message, tx_id
from .utxo import apply_transaction, get_output


def _valid_output(out) -> bool:
    return (isinstance(out, dict) and type(out.get("value")) is int and out["value"] > 0
            and isinstance(out.get("script_pubkey"), list))


def check_transaction(tx: dict, utxo_set: dict) -> tuple[bool, str, int]:
    """Return (ok, reason, fee). Never mutates utxo_set."""
    if not isinstance(tx, dict) or not isinstance(tx.get("inputs"), list) or not isinstance(tx.get("outputs"), list):
        return False, "malformed transaction", 0
    if not tx["inputs"] or not tx["outputs"]:
        return False, "needs at least one input and one output", 0
    if is_coinbase(tx) or "coinbase" in tx:
        return False, "coinbase outside the first slot of a block", 0
    # outputs must be positive integers, or a negative output could offset a
    # huge one and slip past the fee rule
    if not all(_valid_output(o) for o in tx["outputs"]):
        return False, "every output needs a positive integer value and a script", 0

    seen = set()
    for inp in tx["inputs"]:
        key = (inp.get("txid"), inp.get("vout"))
        if key in seen:
            return False, f"input {key[0][:8]}:{key[1]} listed twice (double spend)", 0
        seen.add(key)

    input_sum = 0
    for idx, inp in enumerate(tx["inputs"]):
        prev = get_output(utxo_set, inp["txid"], inp["vout"])
        if prev is None:
            return False, f"input {idx} spends a missing or already-spent coin", 0
        message = signing_message(tx, idx, prev["script_pubkey"])
        if not execute_script(inp.get("script_sig"), prev["script_pubkey"], message):
            return False, f"input {idx} script does not unlock the coin", 0
        input_sum += prev["value"]

    output_sum = sum(o["value"] for o in tx["outputs"])
    if output_sum > input_sum:
        return False, f"outputs {output_sum} exceed inputs {input_sum}", 0
    return True, "ok", input_sum - output_sum


def verify_transaction(tx: dict, utxo_set: dict) -> bool:
    ok, _, _ = check_transaction(tx, utxo_set)
    if ok:
        apply_transaction(utxo_set, tx, tx_id(tx))
    return ok
