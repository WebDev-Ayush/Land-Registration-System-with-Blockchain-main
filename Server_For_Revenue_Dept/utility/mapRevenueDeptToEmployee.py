from web3 import Web3
import os
import json




def mapRevenueDeptIdToEmployee(revenueDeptId,employeeId):
    with open("config.json","r") as f:
        config = json.load(f)


    # Connect to the Ganache network using Web3.py
    ganache_url = config["Ganache_Url"]


    web3 = Web3(Web3.HTTPProvider(ganache_url))


    # Convert addresses to checksum format
    admin_address = web3.to_checksum_address(config["Address_Used_To_Deploy_Contract"])
    web3.eth.default_account = admin_address



    NETWORK_CHAIN_ID = str(config["NETWORK_CHAIN_ID"])

    landRegistryContract = json.loads(
                open(
                        os.getcwd()+
                        "/../"+"Smart_contracts/build/contracts/"+
                        "LandRegistry.json"
                        ).read()
            )
    


    # Load the contract ABI and address from the compiled contract artifacts
    contract_abi = landRegistryContract["abi"]  # Insert the ABI here

    contract_address = web3.to_checksum_address(landRegistryContract["networks"][NETWORK_CHAIN_ID]["address"]) # Insert the contract address here

    # Create a contract instance using the ABI and address
    contract = web3.eth.contract(abi=contract_abi, address=contract_address)


    # Convert employee address to checksum format
    employee_address = web3.to_checksum_address(employeeId)

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
