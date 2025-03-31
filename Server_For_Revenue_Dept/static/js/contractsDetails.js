// Initialize a promise to track contract loading
window.contractsLoaded = new Promise((resolve, reject) => {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/fetchContractDetails', true);

    xhr.onload = function() {
        if (xhr.status === 200) {
            try {
                window.response = JSON.parse(xhr.responseText);
   
                // Users Contract
                window.localStorage.Users_ContractAddress = response["Users"]["address"];
                window.localStorage.Users_ContractABI = JSON.stringify(response["Users"]["abi"]);

                // LandRegistry
                window.localStorage.LandRegistry_ContractAddress = response["LandRegistry"]["address"];
                window.localStorage.LandRegistry_ContractABI = JSON.stringify(response["LandRegistry"]["abi"]);

                // TransferOwnership
                window.localStorage.TransferOwnership_ContractAddress = response["TransferOwnership"]["address"];
                window.localStorage.TransferOwnership_ContractABI = JSON.stringify(response["TransferOwnership"]["abi"]);

                resolve(true);
            } catch (error) {
                console.error('Failed to parse contract details:', error);
                reject(error);
            }
        } else {
            console.error('Request failed. Status:', xhr.status);
            reject(new Error('Failed to fetch contract details'));
        }
    };

    xhr.onerror = function() {
        console.error('Request failed');
        reject(new Error('Network error while fetching contract details'));
    };

    xhr.send();
});





