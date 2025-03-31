async function connectToBlockchain()
{
  notifyUser = document.getElementById("notifyUser");

  // checking Meta-Mask extension is added or not
  if (window.ethereum){
    window.web3 = new Web3(ethereum);

    try{
      showTransactionLoading();
      notifyUser.style.display = "none"; // Clear any previous errors

      // Wait for contract details to be loaded
      if (!window.localStorage.Users_ContractABI || !window.localStorage.Users_ContractAddress) {
        throw new Error('Contract details not loaded. Please refresh the page and try again.');
      }

      // Add timeout for MetaMask connection
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Connection timeout. Please try again.')), 30000);
      });

      // Race between connection and timeout
      await Promise.race([
        window.ethereum.request({
          method: "wallet_requestPermissions",
          params: [
            {
              eth_accounts: {}
            }
          ]
        }),
        timeoutPromise
      ]);

      const accounts = await web3.eth.getAccounts();
      if (!accounts || accounts.length === 0) {
        throw new Error('No accounts found. Please connect your wallet.');
      }

      window.localStorage.setItem("userAddress", accounts[0]);
      window.userAddress = accounts[0];

      // Add timeout for contract interaction
      const contractTimeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Contract interaction timeout. Please try again.')), 30000);
      });

      // Race between contract call and timeout
      const userDetails = await Promise.race([
        (async () => {
          let contractABI = JSON.parse(window.localStorage.Users_ContractABI);
          let contractAddress = window.localStorage.Users_ContractAddress;
          let contract = new window.web3.eth.Contract(contractABI, contractAddress);
          return await contract.methods.users(accounts[0]).call();
        })(),
        contractTimeoutPromise
      ]);

      console.log('User details:', userDetails);

      loadingDiv = document.getElementById("loadingDiv");
      loadingDiv.style.color = "green";

      if (userDetails && userDetails["userID"] == accounts[0]){
        console.log("User Already Registered .. Redirecting to login");
        loadingDiv.innerHTML = `Connected with : ${accounts[0]}
                              <br>
                              Redirecting to Login`;
        window.location.href = "/dashboard";
      } else {
        console.log("User Not registered.. Redirecting to register");
        loadingDiv.innerHTML = `Connected with : ${accounts[0]}
                              <br>
                              Redirecting to Register page`;
        window.location.href = "/register";
      }

    } catch(error){
      console.error('Connection error:', error);
      loadingDiv.style.color = "red";
      loadingDiv.innerHTML = "Connection failed. Please try again.";
      notifyUser.innerText = error.message || "Failed to connect to wallet. Please try again.";
      notifyUser.style.display = "block";
      closeTransactionLoading();
    }

  } else {
    notifyUser.classList.add("alert-danger");
    notifyUser.style.display = "block";
    notifyUser.innerText = "Please Add MetaMask extension for your browser!";
  }
}

function showTransactionLoading(){
  loadingDiv = document.getElementById("loadingDiv");
  loadingDiv.style.display = "block";
}

function closeTransactionLoading(){
  loadingDiv = document.getElementById("loadingDiv");
  loadingDiv.style.display = "none";
}

// show error reason to user
function showError(errorOnTransaction){
  let start = errorOnTransaction.message.indexOf('{'); 
  let end = -1;

  errorObj = JSON.parse( errorOnTransaction.message.slice(start,end));

  errorObj = errorObj.value.data.data;

  txHash = Object.getOwnPropertyNames(errorObj)[0];

  let reason = errorObj[txHash].reason;

  return reason;
}