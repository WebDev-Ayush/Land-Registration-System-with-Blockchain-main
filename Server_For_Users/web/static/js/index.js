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
      if (!window.contractData) {
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

      // Check network ID
      const networkId = await web3.eth.net.getId();
      const networkIdStr = networkId.toString();
      console.log('Current Network ID:', networkIdStr);

      // Verify if contract is deployed on this network
      if (!window.contractData["Users"]["networks"][networkIdStr]) {
        throw new Error(`Smart Contract not found on this network (ID: ${networkIdStr}). Please switch to Ganache.`);
      }

      // Save the correct address for this network to localStorage for other pages
      window.localStorage.Users_ContractAddress = window.contractData["Users"]["networks"][networkIdStr]["address"];
      window.localStorage.Users_ContractABI = JSON.stringify(window.contractData["Users"]["abi"]);
      
      window.localStorage.LandRegistry_ContractAddress = window.contractData["LandRegistry"]["networks"][networkIdStr]["address"];
      window.localStorage.LandRegistry_ContractABI = JSON.stringify(window.contractData["LandRegistry"]["abi"]);
      
      window.localStorage.TransferOwnership_ContractAddress = window.contractData["TransferOwnership"]["networks"][networkIdStr]["address"];
      window.localStorage.TransferOwnership_ContractABI = JSON.stringify(window.contractData["TransferOwnership"]["abi"]);

      const UsersContract = new web3.eth.Contract(
        JSON.parse(window.localStorage.Users_ContractABI), 
        window.localStorage.Users_ContractAddress
      );

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
          console.log('Contract Address:', contractAddress);
          console.log('Using Account:', accounts[0]);
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
      closeTransactionLoading();
      notifyUser.style.display = "block";
      notifyUser.style.color = "red";
      notifyUser.innerHTML = error.message || "Connection failed. Please try again.";
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