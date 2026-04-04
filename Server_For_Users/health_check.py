"""Quick diagnostic: check all blockchain + server health."""
import requests, json

GANACHE = "http://127.0.0.1:7545"
USERS = "http://127.0.0.1:5003"
REVENUE = "http://127.0.0.1:5001"

def rpc(method, params=[]):
    return requests.post(GANACHE, json={"jsonrpc":"2.0","method":method,"params":params,"id":1}).json()["result"]

print("=" * 60)
print("  BLOCKCHAIN SYSTEM HEALTH CHECK")
print("=" * 60)

# 1. Ganache
chain_id = rpc("eth_chainId")
print(f"\n[Ganache] Chain ID: {chain_id} ({int(chain_id, 16)})")
accounts = rpc("eth_accounts")
print(f"[Ganache] Accounts: {len(accounts)}")
for i in range(3):
    bal = int(rpc("eth_getBalance", [accounts[i], "latest"]), 16) / 1e18
    print(f"  [{i}] {accounts[i]}  {bal:.2f} ETH")

# 2. Contract deployment
print(f"\n[Contracts]")
r = requests.get(f"{USERS}/fetchContractDetails")
contracts = r.json()
all_ok = True
for name in ["Users", "LandRegistry", "TransferOwnership"]:
    addr = contracts[name]["address"]
    code = rpc("eth_getCode", [addr, "latest"])
    deployed = len(code) > 4
    status = "DEPLOYED" if deployed else "MISSING"
    if not deployed:
        all_ok = False
    print(f"  {name}: {addr} -> {status}")

# 3. Users server
print(f"\n[Users Server - port 5003]")
r = requests.get(f"{USERS}/")
print(f"  Home: {r.status_code}")
r = requests.get(f"{USERS}/fetchContractDetails")
print(f"  Contract details: {r.status_code}")
r = requests.get(f"{USERS}/propertyFinder")
print(f"  Property Finder: {r.status_code}")
r = requests.get(f"{USERS}/api/metrics")
print(f"  ML Metrics: {r.status_code}")

# 4. Revenue server
print(f"\n[Revenue Dept Server - port 5001]")
r = requests.get(f"{REVENUE}/")
print(f"  Home: {r.status_code}")
r = requests.get(f"{REVENUE}/fetchContractDetails")
print(f"  Contract details: {r.status_code}")
r = requests.get(f"{REVENUE}/admin")
print(f"  Admin page: {r.status_code}")

# 5. Check key pages
print(f"\n[Frontend Pages]")
pages_users = ["/", "/register", "/dashboard", "/availableToBuy", "/MySales", "/myRequestedSales", "/propertyFinder"]
for p in pages_users:
    try:
        r = requests.get(f"{USERS}{p}", timeout=3)
        print(f"  Users{p}: {r.status_code}")
    except:
        print(f"  Users{p}: FAILED")

pages_rev = ["/", "/admin"]
for p in pages_rev:
    try:
        r = requests.get(f"{REVENUE}{p}", timeout=3)
        print(f"  Revenue{p}: {r.status_code}")
    except:
        print(f"  Revenue{p}: FAILED")

# 6. Check Revenue dept CWD issue
print(f"\n[Revenue Dept Config]")
r2 = requests.get(f"{REVENUE}/fetchContractDetails")
rd = r2.json()
if "error" in rd:
    print(f"  ERROR: {rd['error']}")
else:
    print(f"  OK - all contracts loaded")

print(f"\n{'=' * 60}")
if all_ok:
    print("  ALL SYSTEMS OPERATIONAL")
else:
    print("  ISSUES DETECTED - see above")
print(f"{'=' * 60}")
