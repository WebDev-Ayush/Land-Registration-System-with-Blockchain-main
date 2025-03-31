from flask import Flask, jsonify, render_template, request, Response, redirect
from pymongo import MongoClient
import gridfs
from web3 import Web3, HTTPProvider
import json
import os

# blockchain Network ID - update to match the network ID from the deployment
NETWORK_CHAIN_ID = "1337"  # Changed from "5777" to "1337" to match the deployment

# connect to MongoDB
client = MongoClient('mongodb://localhost:27017')

# connect to database
LandRegistryDB = client.LandRegistry

# connect to file system
fs = gridfs.GridFS(LandRegistryDB)

# connect to collection
propertyDocsTable = LandRegistryDB.Property_Docs

app = Flask(
    __name__,
    static_url_path='', 
    static_folder='web/static',
    template_folder='web/templates'
)

# Configure JSON responses
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json'

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register')
def register():
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html',add_property=True)



@app.route('/uploadPropertyDocs', methods=['POST'])
def upload():
    # Get the uploaded files and form data from the request
    registraionDocs = request.files['propertyDocs']
    owner = request.form['owner']
    propertyId = request.form['propertyId']

    # Do something with the uploaded files and form data

    try:
        file_id = fs.put(registraionDocs, filename="%s_%s.pdf"%(owner,propertyId))
        rowId = propertyDocsTable.insert_one({
                                            "Owner":owner,
                                            "Property_Id":propertyId,
                                            "%s_%s.pdf"%(owner,propertyId):file_id
                                        }).inserted_id

    except errors.PyMongoError as e:
        # Return a response to the client
        return jsonify({'status': 'Failed Uploading Files','fileId':str(0)})
    else:
        return jsonify({'status': 'success','fileId':str(file_id)})


@app.route('/propertiesDocs/pdf/<propertyId>')
def get_pdf(propertyId):
  try:
    try:
        propertyDetails = propertyDocsTable.find({"Property_Id":"%s"%(propertyId)})[0]

    except IndexError as e:
        return jsonify({"status":0,"Reason":"No Property Matched With Id"})

    fileName = "%s_%s.pdf"%(propertyDetails['Owner'],propertyDetails['Property_Id'])

    file = fs.get(propertyDetails[fileName])

    response = Response(file, content_type='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename="{file.filename}"'

    return response

  except Exception as e:
    return jsonify({"status":0,"Reason":str(e)})


@app.route('/fetchContractDetails')
def fetchContractDetails():
    try:
        # Verify Ganache connection
        w3 = Web3(HTTPProvider('http://127.0.0.1:7545'))
        try:
            if not w3.is_connected():
                print("Failed to connect to Ganache")
                return jsonify({"error": "Cannot connect to Ganache. Please make sure Ganache is running on port 7545."}), 500
            print("Successfully connected to Ganache")
        except Exception as e:
            print(f"Error connecting to Ganache: {str(e)}")
            return jsonify({"error": f"Error connecting to Ganache: {str(e)}"}), 500

        # Get the absolute path to the contracts directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        contracts_dir = os.path.join(base_dir, "Smart_contracts", "build", "contracts")
        print(f"Looking for contracts in: {contracts_dir}")

        # Read contract files
        users_contract_path = os.path.join(contracts_dir, "Users.json")
        land_registry_contract_path = os.path.join(contracts_dir, "LandRegistry.json")
        transfer_ownership_contract_path = os.path.join(contracts_dir, "TransferOwnerShip.json")

        # Check if files exist
        if not os.path.exists(users_contract_path):
            print(f"Users contract file not found at: {users_contract_path}")
            return jsonify({"error": "Users contract file not found"}), 500
        if not os.path.exists(land_registry_contract_path):
            print(f"LandRegistry contract file not found at: {land_registry_contract_path}")
            return jsonify({"error": "LandRegistry contract file not found"}), 500
        if not os.path.exists(transfer_ownership_contract_path):
            print(f"TransferOwnership contract file not found at: {transfer_ownership_contract_path}")
            return jsonify({"error": "TransferOwnership contract file not found"}), 500

        # Read and parse contract files
        try:
            with open(users_contract_path, 'r') as f:
                usersContract = json.load(f)
            with open(land_registry_contract_path, 'r') as f:
                landRegistryContract = json.load(f)
            with open(transfer_ownership_contract_path, 'r') as f:
                transferOwnerShip = json.load(f)
            print("Successfully loaded contract files")
        except Exception as e:
            print(f"Error loading contract files: {str(e)}")
            return jsonify({"error": f"Error loading contract files: {str(e)}"}), 500

        # Check if network exists
        if NETWORK_CHAIN_ID not in usersContract["networks"]:
            print(f"Users contract not deployed to network {NETWORK_CHAIN_ID}")
            return jsonify({"error": f"Users contract not deployed to network {NETWORK_CHAIN_ID}"}), 500
        if NETWORK_CHAIN_ID not in landRegistryContract["networks"]:
            print(f"LandRegistry contract not deployed to network {NETWORK_CHAIN_ID}")
            return jsonify({"error": f"LandRegistry contract not deployed to network {NETWORK_CHAIN_ID}"}), 500
        if NETWORK_CHAIN_ID not in transferOwnerShip["networks"]:
            print(f"TransferOwnership contract not deployed to network {NETWORK_CHAIN_ID}")
            return jsonify({"error": f"TransferOwnership contract not deployed to network {NETWORK_CHAIN_ID}"}), 500

        # Verify contract addresses
        users_address = usersContract["networks"][NETWORK_CHAIN_ID]["address"]
        land_registry_address = landRegistryContract["networks"][NETWORK_CHAIN_ID]["address"]
        transfer_ownership_address = transferOwnerShip["networks"][NETWORK_CHAIN_ID]["address"]

        print(f"Users contract address: {users_address}")
        print(f"LandRegistry contract address: {land_registry_address}")
        print(f"TransferOwnership contract address: {transfer_ownership_address}")

        # Check if contracts exist at the addresses
        try:
            users_code = w3.eth.get_code(users_address)
            land_registry_code = w3.eth.get_code(land_registry_address)
            transfer_ownership_code = w3.eth.get_code(transfer_ownership_address)

            if not users_code:
                print(f"Users contract not found at address: {users_address}")
                return jsonify({"error": "Users contract not found at specified address"}), 500
            if not land_registry_code:
                print(f"LandRegistry contract not found at address: {land_registry_address}")
                return jsonify({"error": "LandRegistry contract not found at specified address"}), 500
            if not transfer_ownership_code:
                print(f"TransferOwnership contract not found at address: {transfer_ownership_address}")
                return jsonify({"error": "TransferOwnership contract not found at specified address"}), 500
        except Exception as e:
            print(f"Error checking contract addresses: {str(e)}")
            return jsonify({"error": f"Error checking contract addresses: {str(e)}"}), 500

        response = {
            "Users": {
                "address": users_address,
                "abi": usersContract["abi"]
            },
            "LandRegistry": {
                "address": land_registry_address,
                "abi": landRegistryContract["abi"]
            },
            "TransferOwnership": {
                "address": transfer_ownership_address,
                "abi": transferOwnerShip["abi"]
            }
        }

        print("Successfully prepared contract details")
        return jsonify(response)

    except Exception as e:
        print(f"Error in fetchContractDetails: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/logout')
def logout():
    return redirect('/')

@app.route('/availableToBuy')
def availableToBuy():
    return render_template('availableToBuy.html')


@app.route('/MySales')
def MySales():
    return render_template('mySales.html')

@app.route('/myRequestedSales')
def myRequestedSales():
    return render_template('myRequestedSales.html')

@app.route('/example')
def example():
    return render_template('example.html')  # Ensure this is complete

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
