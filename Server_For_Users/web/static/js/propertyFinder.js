/* ─── AI Property Finder ─── */

async function checkConnection() {
    if (window.ethereum) {
        try {
            window.web3 = new Web3(ethereum);
            const accounts = await web3.eth.getAccounts();
            const account = accounts[0];

            if (account != window.localStorage["userAddress"]) {
                alert("Mismatch in account used to login and connected to MetaMask. Please login again.");
                window.location.href = "/";
            } else {
                fetchUserDetails();
            }
        } catch (error) {
            alert(error);
        }
    } else {
        alert("Please add MetaMask extension for your browser!");
    }
}

async function fetchUserDetails() {
    let contractABI = JSON.parse(window.localStorage.Users_ContractABI);
    let contractAddress = window.localStorage.Users_ContractAddress;
    let contract = new window.web3.eth.Contract(contractABI, contractAddress);
    let account = window.localStorage["userAddress"];

    let user = await contract.methods.users(account).call();
    if (user["userID"] == account) {
        document.getElementById("nameOfUser").innerText = user["firstName"];
    }
}


/**
 * Gather form inputs, call the /api/recommend endpoint, and render results.
 */
async function getRecommendations(event) {
    event.preventDefault();

    const btn = document.getElementById("searchBtn");
    const btnText = document.getElementById("searchBtnText");
    const btnLoad = document.getElementById("searchBtnLoading");

    // Show loading state
    btnText.style.display = "none";
    btnLoad.style.display = "inline-flex";
    btn.disabled = true;

    // Collect selected facilities
    const facilityCheckboxes = document.querySelectorAll('.pf-facilities-grid input[type="checkbox"]:checked');
    const facilities = Array.from(facilityCheckboxes).map(cb => cb.value);

    // Build query payload
    const query = {
        budget:       parseFloat(document.getElementById("budget").value) || 0,
        minArea:      parseFloat(document.getElementById("minArea").value) || 0,
        bedrooms:     parseInt(document.getElementById("bedrooms").value) || 0,
        bathrooms:    parseInt(document.getElementById("bathrooms").value) || 0,
        propertyType: document.getElementById("propertyType").value,
        areaType:     document.getElementById("areaType").value,
        furnished:    document.getElementById("furnished").value,
        parking:      document.getElementById("parking").value === "true",
        yearBuilt:    parseInt(document.getElementById("yearBuilt").value) || 2020,
        facilities:   facilities,
        topN:         10
    };

    try {
        const resp = await fetch("/api/recommend", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(query)
        });

        const data = await resp.json();

        if (data.error) {
            alert("Error: " + data.error);
            return;
        }

        renderResults(data.results);

    } catch (err) {
        alert("Failed to get recommendations: " + err.message);
    } finally {
        // Reset button
        btnText.style.display = "inline";
        btnLoad.style.display = "none";
        btn.disabled = false;
    }
}


/**
 * Render the array of property results as cards.
 */
function renderResults(results) {
    const grid     = document.getElementById("resultsGrid");
    const section  = document.getElementById("resultsSection");
    const noRes    = document.getElementById("noResults");
    const countEl  = document.getElementById("resultCount");

    grid.innerHTML = "";

    if (!results || results.length === 0) {
        section.style.display = "none";
        noRes.style.display   = "block";
        return;
    }

    noRes.style.display   = "none";
    section.style.display = "block";
    countEl.textContent   = `(${results.length} found)`;

    results.forEach((prop, idx) => {
        grid.appendChild(createCard(prop, idx + 1));
    });

    // Smooth scroll to results
    section.scrollIntoView({ behavior: "smooth", block: "start" });
}


/**
 * Build a single property card DOM element.
 */
function createCard(prop, rank) {
    const card = document.createElement("div");
    card.className = "pf-card";

    // Match score colour class
    let matchClass = "pf-match-low";
    if (prop.matchScore >= 70) matchClass = "pf-match-high";
    else if (prop.matchScore >= 40) matchClass = "pf-match-medium";

    // Format property type
    const ptLabel = (prop.propertyType || "").replace(/_/g, " ")
                        .replace(/\b\w/g, c => c.toUpperCase());

    // Format facilities
    const facilityHTML = (prop.facilities || []).map(f => {
        const label = f.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
        return `<span class="pf-facility">${label}</span>`;
    }).join("");

    card.innerHTML = `
        <div class="pf-card-header">
            <p class="pf-card-title">#${rank} ${prop.title || "Property " + prop.propertyId}</p>
            <p class="pf-card-city">${prop.city || "Location " + prop.locationId}</p>
            <span class="pf-match-badge ${matchClass}">${prop.matchScore}% Match</span>
        </div>
        <div class="pf-card-body">
            <p class="pf-card-desc">${prop.description || ""}</p>

            <div class="pf-card-stats">
                <div class="pf-stat">
                    <div class="pf-stat-value">${prop.price} ETH</div>
                    <div class="pf-stat-label">Price</div>
                </div>
                <div class="pf-stat">
                    <div class="pf-stat-value">${prop.area} ft&sup2;</div>
                    <div class="pf-stat-label">Area</div>
                </div>
                <div class="pf-stat">
                    <div class="pf-stat-value">${prop.bedrooms || 0}</div>
                    <div class="pf-stat-label">Bedrooms</div>
                </div>
                <div class="pf-stat">
                    <div class="pf-stat-value">${prop.bathrooms || 0}</div>
                    <div class="pf-stat-label">Bathrooms</div>
                </div>
            </div>

            <div class="pf-tags">
                ${ptLabel ? `<span class="pf-tag pf-tag-type">${ptLabel}</span>` : ""}
                ${prop.areaType ? `<span class="pf-tag pf-tag-area">${prop.areaType}</span>` : ""}
                ${prop.furnished ? `<span class="pf-tag pf-tag-furn">${prop.furnished}</span>` : ""}
                ${prop.parking ? `<span class="pf-tag pf-tag-parking">Parking</span>` : ""}
                ${prop.yearBuilt ? `<span class="pf-tag pf-tag-type">Built ${prop.yearBuilt}</span>` : ""}
            </div>

            <div class="pf-card-facilities">${facilityHTML}</div>
        </div>
    `;

    return card;
}


/* ─── Model Transparency Panel ─── */

function toggleModelInfo() {
    const panel = document.getElementById("modelInfoPanel");
    if (panel.style.display === "none") {
        panel.style.display = "block";
        loadModelInfo();
    } else {
        panel.style.display = "none";
    }
}

async function loadModelInfo() {
    const container = document.getElementById("modelInfoContent");

    try {
        const resp = await fetch("/api/metrics");
        if (!resp.ok) {
            container.innerHTML = `<p class="pf-info-error">Model not trained yet. Start the server to auto-train.</p>`;
            return;
        }
        const m = await resp.json();

        // Also fetch listing count
        const listResp = await fetch("/api/listings");
        const listData = await listResp.json();

        const r2Pct = (m.r2 * 100).toFixed(1);
        const cvPct = (m.cv_r2_mean * 100).toFixed(1);

        // Build feature importance bars
        const topFeatures = Object.entries(m.feature_importances_top10 || {});
        const maxImp = topFeatures.length > 0 ? topFeatures[0][1] : 1;
        const featureBarsHTML = topFeatures.map(([name, imp]) => {
            const pct = ((imp / maxImp) * 100).toFixed(0);
            const label = name.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
            return `<div class="pf-imp-row">
                <span class="pf-imp-label">${label}</span>
                <div class="pf-imp-bar-bg"><div class="pf-imp-bar" style="width:${pct}%"></div></div>
                <span class="pf-imp-val">${(imp * 100).toFixed(1)}%</span>
            </div>`;
        }).join("");

        container.innerHTML = `
            <div class="pf-info-grid">
                <div class="pf-info-section">
                    <h4>&#x1F4D6; Where Does the Data Come From?</h4>
                    <ul>
                        <li><strong>Property listings</strong> are stored in <strong>MongoDB</strong> (collection: PropertyListings).
                            Currently <strong>${listData.count}</strong> properties are on-sale.</li>
                        <li>When a seller lists a property on the blockchain and marks it for sale,
                            the property metadata (price, area, type, facilities, etc.) is saved to MongoDB.</li>
                        <li><strong>Training data</strong> is synthetically generated: <strong>${m.n_training_samples.toLocaleString()}</strong>
                            random (buyer_query, property) pairs are created, and a <em>domain-rule relevance score</em>
                            (0–100) is computed based on budget fit, bedroom match, facility overlap, etc. — with Gaussian noise added
                            so the model must learn patterns rather than memorise rules.</li>
                        <li>This is a standard approach for <strong>cold-start recommendation systems</strong> where real user
                            interaction data does not yet exist.</li>
                    </ul>
                </div>

                <div class="pf-info-section">
                    <h4>&#x2699;&#xFE0F; How Does the Model Work?</h4>
                    <ul>
                        <li><strong>Algorithm:</strong> Gradient Boosting Regressor (scikit-learn)</li>
                        <li><strong>Features per pair:</strong> ${m.n_features} columns — including price ratio, area ratio,
                            bedroom/bathroom differences, type/area/furnishing match flags, facility overlap ratio,
                            and one-hot encodings.</li>
                        <li><strong>Scaling:</strong> StandardScaler (zero mean, unit variance)</li>
                        <li>At inference time, each on-sale property is paired with your query, features are computed,
                            and the trained model predicts a match score (0–100). Results are sorted by score.</li>
                    </ul>
                </div>

                <div class="pf-info-section">
                    <h4>&#x1F4CA; Model Accuracy & Metrics</h4>
                    <div class="pf-metrics-grid">
                        <div class="pf-metric-card">
                            <div class="pf-metric-value pf-metric-good">${r2Pct}%</div>
                            <div class="pf-metric-label">R² Score (Test)</div>
                            <div class="pf-metric-desc">Variance explained</div>
                        </div>
                        <div class="pf-metric-card">
                            <div class="pf-metric-value">${m.mae}</div>
                            <div class="pf-metric-label">MAE (Test)</div>
                            <div class="pf-metric-desc">Mean absolute error on 0-100 scale</div>
                        </div>
                        <div class="pf-metric-card">
                            <div class="pf-metric-value">${m.rmse}</div>
                            <div class="pf-metric-label">RMSE (Test)</div>
                            <div class="pf-metric-desc">Root mean squared error</div>
                        </div>
                        <div class="pf-metric-card">
                            <div class="pf-metric-value pf-metric-good">${cvPct}%</div>
                            <div class="pf-metric-label">5-Fold CV R²</div>
                            <div class="pf-metric-desc">&plusmn; ${(m.cv_r2_std * 100).toFixed(2)}% (stable)</div>
                        </div>
                    </div>
                </div>

                <div class="pf-info-section">
                    <h4>&#x1F3AF; Top Feature Importances</h4>
                    <p class="pf-info-small">What the model cares about most when scoring:</p>
                    <div class="pf-imp-chart">${featureBarsHTML}</div>
                </div>

                <div class="pf-info-section">
                    <h4>&#x2705; Is the Data Verified?</h4>
                    <ul>
                        <li><strong>Property ownership</strong> is verified on the Ethereum blockchain —
                            the smart contract ensures only verified owners can list properties for sale.</li>
                        <li><strong>Property metadata</strong> (price, area, facilities) is entered by the seller
                            and stored in MongoDB. It is cross-referenced with the blockchain property ID.</li>
                        <li><strong>Training labels</strong> are generated from expert domain rules
                            (budget check, area check, type match, facility overlap) — not from unverified user clicks.</li>
                        <li>The model can be <strong>retrained at any time</strong> via the <code>POST /api/train</code>
                            endpoint as more real data becomes available.</li>
                    </ul>
                </div>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<p class="pf-info-error">Failed to load model info: ${err.message}</p>`;
    }
}
