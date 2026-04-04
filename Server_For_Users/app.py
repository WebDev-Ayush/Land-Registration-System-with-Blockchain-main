from flask import Flask, jsonify, render_template, request, Response, redirect
from pymongo import MongoClient
import gridfs
from web3 import Web3, HTTPProvider
import json
import os
from ml_recommender import recommend, seed_sample_data, train_model, get_model_metrics

# blockchain Network ID - update to match the network ID from the deployment
NETWORK_CHAIN_ID = "1775301245182"  # Must match the Ganache network ID from truffle migrate

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
        # Get the absolute path to the contracts directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        contracts_dir = os.path.join(base_dir, "Smart_contracts", "build", "contracts")

        with open(os.path.join(contracts_dir, "Users.json"), 'r') as f:
            usersContract = json.load(f)
        with open(os.path.join(contracts_dir, "LandRegistry.json"), 'r') as f:
            landRegistryContract = json.load(f)
        with open(os.path.join(contracts_dir, "TransferOwnerShip.json"), 'r') as f:
            transferOwnerShip = json.load(f)

        response = {
            "Users": {
                "address": usersContract["networks"][NETWORK_CHAIN_ID]["address"],
                "abi": usersContract["abi"]
            },
            "LandRegistry": {
                "address": landRegistryContract["networks"][NETWORK_CHAIN_ID]["address"],
                "abi": landRegistryContract["abi"]
            },
            "TransferOwnership": {
                "address": transferOwnerShip["networks"][NETWORK_CHAIN_ID]["address"],
                "abi": transferOwnerShip["abi"]
            }
        }

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


# ── ML Property Recommendation ─────────────────────────────────────────

@app.route('/propertyFinder')
def propertyFinder():
    return render_template('propertyFinder.html')


@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    """Accept buyer preferences JSON and return ranked property recommendations."""
    try:
        query = request.get_json(silent=True)
        if not query:
            return jsonify({"error": "No JSON body provided. Send Content-Type: application/json with a JSON body."}), 400

        top_n = int(query.pop("topN", 10))
        results = recommend(query, top_n=top_n)
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        print(f"Error in /api/recommend: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/listings', methods=['GET'])
def api_listings():
    """Return all on-sale property listings from MongoDB."""
    try:
        db = client.LandRegistry
        listings = list(db.PropertyListings.find({"onSale": True}))
        for l in listings:
            l.pop("_id", None)
        return jsonify({"listings": listings, "count": len(listings)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/listings', methods=['POST'])
def api_add_listing():
    """Add a new property listing to MongoDB."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body"}), 400
        data["onSale"] = True
        db = client.LandRegistry
        db.PropertyListings.insert_one(data)
        data.pop("_id", None)
        return jsonify({"status": "success", "listing": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/seed', methods=['POST'])
def api_seed():
    """Seed sample property listings for demo."""
    try:
        msg = seed_sample_data()
        return jsonify({"message": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/metrics', methods=['GET'])
def api_metrics():
    """Return the trained model's evaluation metrics."""
    try:
        metrics = get_model_metrics()
        if metrics is None:
            return jsonify({"error": "Model not trained yet"}), 404
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/train', methods=['POST'])
def api_train():
    """Retrain the ML model and return updated metrics."""
    try:
        data = request.get_json() or {}
        n_samples = int(data.get("n_samples", 10000))
        metrics = train_model(n_samples=n_samples, verbose=True)
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Auto-seed sample data and train model on first run
    seed_sample_data()
    train_model(n_samples=10000, verbose=True)
    app.run(debug=True, host='0.0.0.0', port=5003)


