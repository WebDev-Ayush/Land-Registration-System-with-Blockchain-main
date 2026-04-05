



var xhr = new XMLHttpRequest();

xhr.open('GET', '/fetchContractDetails', true);

xhr.onload = function () {
  if (xhr.status === 200) {

    window.contractData = JSON.parse(xhr.responseText);
    console.log("Contract details loaded successfully.");

  } else {
    console.log('Request failed.  Returned status of ' + xhr.status);
  }
};

xhr.send();








async function logout() {


  const provider = window.ethereum;

  // Check if the provider is available
  if (provider) {
    try {
      await provider.disconnect();
      console.log("Disconnected from provider.");
    } catch (err) {
      console.error(err);
    }
  }
  else {
    console.log("Provider not available.");
  }


}