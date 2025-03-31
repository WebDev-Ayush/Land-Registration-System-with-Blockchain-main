async function connectToBlockchain() {
  // checking Meta-Mask extension is added or not
  if (typeof window.ethereum !== 'undefined') {
    try {
      alertUser('','alert-info','none');
      showTransactionLoading();
      document.getElementById("loadingDiv").innerHTML = "Loading contracts...";

      // Wait for contracts to load first
      await window.contractsLoaded;
      
      document.getElementById("loadingDiv").innerHTML = "Connecting to MetaMask...";

      // Force disconnect first to ensure popup
      await window.ethereum.request({
        method: "wallet_requestPermissions",
        params: [{
          eth_accounts: {}
        }]
      });

      // Request account access
      const accounts = await window.ethereum.request({ 
        method: 'eth_requestAccounts' 
      });

      if (!accounts || accounts.length === 0) {
        throw new Error('No accounts found');
      }

      // Switch to Ganache network
      try {
        await window.ethereum.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: '0x539' }], // 1337 in hex
        });
      } catch (switchError) {
        // If chain hasn't been added, add it
        if (switchError.code === 4902) {
          try {
            await window.ethereum.request({
              method: 'wallet_addEthereumChain',
              params: [
                {
                  chainId: '0x539', // 1337 in hex
                  chainName: 'Ganache',
                  rpcUrls: ['http://0.0.0.0:7545'],
                  nativeCurrency: {
                    name: 'ETH',
                    symbol: 'ETH',
                    decimals: 18
                  }
                }
              ]
            });
          } catch (addError) {
            throw addError;
          }
        } else {
          throw switchError;
        }
      }

      // Initialize Web3
      window.web3 = new Web3(window.ethereum);

      // Store the connected account
      window.localStorage.setItem("employeeId", accounts[0].toLowerCase()); // Convert to lowercase
      window.employeeId = accounts[0].toLowerCase(); // Convert to lowercase

      // Update UI
      const loadingDiv = document.getElementById("loadingDiv");
      loadingDiv.style.color = "green";
      loadingDiv.innerHTML = `Connected with : ${accounts[0]}<br>Enter Password`;

      document.getElementById("connectToBlockchainDiv").style.display = "none";
      document.getElementById("passwordDiv").style.display = "block";
      document.getElementById("loadingDiv").style.display = "none";

      alertUser('Enter Your Password','alert-success','block');

    } catch (error) {
      console.error("Connection error:", error);
      document.getElementById("loadingDiv").style.display = "none";
      if (error.code === 4001) {
        alertUser('Please connect your wallet to continue','alert-danger','block');
      } else if (error.message === 'No accounts found') {
        alertUser('No accounts found in MetaMask. Please add an account.','alert-danger','block');
      } else {
        alertUser('Failed to connect wallet. Please try again.','alert-danger','block');
      }
    }
  } else {
    alertUser('Please install MetaMask to use this application','alert-danger','block');
  }
}

function login() {
  let employeeId = window.localStorage["employeeId"].toLowerCase(); // Convert to lowercase
  let password = document.getElementById("password").value;

  console.log("Attempting login with:", {
    employeeId: employeeId,
    password: password
  });

  // Create a new FormData object
  const formData = new FormData();

  // Append the files and data to the FormData object
  formData.append('employeeId', employeeId);
  formData.append('password', password);

  // Send a POST request to the Flask server
  fetch('/login', {
    method: 'POST',
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      // Handle the response from the Flask server
      console.log("Server response:", data);

      let status = data['status'];
      let msg = data['msg'];

      if (status == 1) {
        console.log("Login successful:", msg);
        let revenueDepartmentId = data["revenueDepartmentId"];
        window.localStorage.revenueDepartmentId = revenueDepartmentId;
        window.localStorage.empName = data['empName'];
        window.location.href = "/dashboard";
      }
      else {
        console.log("Login failed:", msg);
        alertUser(msg,'alert-danger','block');
      }
    })
    .catch(error => {
      console.error("Login request failed:", error);
    });
}

function showTransactionLoading() {
  const loadingDiv = document.getElementById("loadingDiv");
  loadingDiv.style.display = "block";
  loadingDiv.style.color = "black";
}

function closeTransactionLoading() {
  const loadingDiv = document.getElementById("loadingDiv");
  loadingDiv.style.display = "none";
}

// show error reason to user
function showError(errorOnTransaction) {


  errorCode = errorOnTransaction.code;

  if(errorCode==4001){
    return "Rejected Transaction";
  }
  else{
    let start = errorOnTransaction.message.indexOf('{');
    let end = -1;
  
    errorObj = JSON.parse(errorOnTransaction.message.slice(start, end));
  
    errorObj = errorObj.value.data.data;
  
    txHash = Object.getOwnPropertyNames(errorObj)[0];
  
    let reason = errorObj[txHash].reason;
  
    return reason;
  }
}


function alertUser(msg,msgType,display){

  console.log(msg,display);
  notifyUser = document.getElementById("notifyUser");

  notifyUser.classList = [];
  notifyUser.classList.add("alert");
  notifyUser.classList.add(msgType);
  notifyUser.innerText = msg;
  notifyUser.style.display = display;


  
}

