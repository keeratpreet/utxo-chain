"""
UTXO set: {(txid, vout): {"value": int, "script_pubkey": list}}.
"""


def get_output(utxo_set: dict, txid: str, vout: int) -> dict | None:
    return utxo_set.get((txid, vout))


def spend_output(utxo_set: dict, txid: str, vout: int) -> None:
    utxo_set.pop((txid, vout), None)


def add_output(utxo_set: dict, txid: str, vout: int, value: int, script_pubkey: list) -> None:
    utxo_set[(txid, vout)] = {"value": value, "script_pubkey": script_pubkey}


def apply_transaction(utxo_set: dict, tx: dict, txid: str) -> None:
    """Spend the inputs and add the outputs (call only after the tx is verified)."""
    for inp in tx["inputs"]:
        spend_output(utxo_set, inp["txid"], inp["vout"])
    for i, out in enumerate(tx["outputs"]):
        add_output(utxo_set, txid, i, out["value"], out["script_pubkey"])
