from web3 import Web3
import os
import json




def mapRevenueDeptIdToEmployee(revenueDeptId,employeeId):
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    with open(config_path,"r") as f:
        config = json.load(f)


    # Connect to the Ganache network using Web3.py
    ganache_url = config["Ganache_Url"]


    web3 = Web3(Web3.HTTPProvider(ganache_url))


    # Convert addresses to checksum format
    admin_address = web3.toChecksumAddress(config["Address_Used_To_Deploy_Contract"])
    web3.eth.default_account = admin_address



    NETWORK_CHAIN_ID = str(config["NETWORK_CHAIN_ID"])

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    contracts_path = os.path.join(base_dir, "Smart_contracts", "build", "contracts", "LandRegistry.json")

    landRegistryContract = json.loads(
                open(contracts_path).read()
            )
    


    # Load the contract ABI and address from the compiled contract artifacts
    contract_abi = landRegistryContract["abi"]  # Insert the ABI here

    contract_address = web3.toChecksumAddress(landRegistryContract["networks"][NETWORK_CHAIN_ID]["address"]) # Insert the contract address here

    # Create a contract instance using the ABI and address
    contract = web3.eth.contract(abi=contract_abi, address=contract_address)


    # Convert employee address to checksum format
    employee_address = web3.toChecksumAddress(employeeId)

    # Call the mapRevenueDeptIdToEmployee function with the desired parameters
    try:
        txn_hash = contract.functions.mapRevenueDeptIdToEmployee(
            int(revenueDeptId), 
            employee_address
        ).transact({'from': admin_address})
        
        # Wait for the transaction to be mined
        receipt = web3.eth.wait_for_transaction_receipt(txn_hash)

        # successful transaction
        if receipt['status'] == 1:
            return True
        else:
            return False
    except Exception as e:
        print(f"Transaction failed: {str(e)}")
        return False
