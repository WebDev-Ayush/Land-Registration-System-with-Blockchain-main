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

      // Switch to Ganache network (chainId 0x539 = 1337)
      try {
        await window.ethereum.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: '0x539' }],
        });
      } catch (switchError) {
        if (switchError.code === 4902) {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [{
              chainId: '0x539',
              chainName: 'Ganache Local',
              rpcUrls: ['http://127.0.0.1:7545'],
              nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 }
            }]
          });
        } else {
          throw switchError;
        }
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
      console.log('Current Network ID:', networkId);
      if (networkId !== 1337) {
        try {
          // Attempt to switch to Ganache network (1337)
          await window.ethereum.request({
            method: 'wallet_switchEthereumChain',
            params: [{ chainId: '0x539' }], // 1337 in hex
          });
        } catch (switchError) {
          // This error code indicates that the chain has not been added to MetaMask.
          if (switchError.code === 4902) {
            try {
              await window.ethereum.request({
                method: 'wallet_addEthereumChain',
                params: [
                  {
                    chainId: '0x539',
                    chainName: 'Ganache',
                    rpcUrls: ['http://127.0.0.1:7545'],
                    nativeCurrency: {
                      name: 'Ether',
                      symbol: 'ETH',
                      decimals: 18
                    }
                  },
                ],
              });
            } catch (addError) {
              throw new Error('Please switch to Ganache network (1337) in MetaMask.');
            }
          } else {
            throw new Error('Please switch to Ganache network (1337) in MetaMask.');
          }
        }
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
      loadingDiv.style.color = "red";
      loadingDiv.innerHTML = "Connection failed. Please try again.";
      
      let errorMsg = error.message || "Failed to connect to wallet. Please try again.";
      if (errorMsg.includes("Returned values aren't valid")) {
        errorMsg = "Smart Contract not found. Please make sure your MetaMask is connected to the Ganache network (http://127.0.0.1:7545) and the contracts are deployed.";
      }
      
      notifyUser.innerText = errorMsg;
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