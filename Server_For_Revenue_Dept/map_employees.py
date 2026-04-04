"""Map seeded employees to their revenue departments on the blockchain."""
import json, os, sys
from web3 import Web3

# Navigate to Revenue Dept directory for config
REVENUE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(REVENUE_DIR)

config_path = os.path.join(REVENUE_DIR, "config.json")
with open(config_path) as f:
    config = json.load(f)

w3 = Web3(Web3.HTTPProvider(config["Ganache_Url"]))
admin = w3.toChecksumAddress(config["Address_Used_To_Deploy_Contract"])
w3.eth.default_account = admin

NETWORK_ID = str(config["NETWORK_CHAIN_ID"])
contracts_dir = os.path.join(BASE_DIR, "Smart_contracts", "build", "contracts")

with open(os.path.join(contracts_dir, "LandRegistry.json")) as f:
    lr = json.load(f)

contract = w3.eth.contract(
    address=w3.toChecksumAddress(lr["networks"][NETWORK_ID]["address"]),
    abi=lr["abi"],
)

EMPLOYEES = [
    ("101", "0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0"),
    ("102", "0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b"),
    ("103", "0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d"),
]

for dept_id, addr in EMPLOYEES:
    emp_addr = w3.toChecksumAddress(addr)
    try:
        tx = contract.functions.mapRevenueDeptIdToEmployee(int(dept_id), emp_addr).transact({"from": admin})
        receipt = w3.eth.wait_for_transaction_receipt(tx)
        status = "OK" if receipt["status"] == 1 else "FAILED"
        print(f"  Dept {dept_id} -> {addr[:10]}... : {status}")
    except Exception as e:
        msg = str(e)
        if "already mapped" in msg.lower() or "revert" in msg.lower():
            print(f"  Dept {dept_id} -> {addr[:10]}... : Already mapped (OK)")
        else:
            print(f"  Dept {dept_id} -> {addr[:10]}... : ERROR: {msg}")

print("\nDone mapping employees to revenue departments on blockchain.")
