const API_URL = "http://127.0.0.1:50505";
const currentDomain = window.location.hostname || "localhost";
let usedSuggestedPassword = false;

// Locate the username/email input field associated with the password field
function findUsernameInput(passwordInput) {
    const form = passwordInput.closest("form") || document.body;
    const inputs = Array.from(form.querySelectorAll('input[type="text"], input[type="email"], input:not([type])'));
    return inputs.find(el => el.offsetParent !== null) || null;
}

// Communicate with the local desktop vault application
async function callVault(payload) {
    try {
        const res = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        return await res.json();
    } catch (e) {
        return { status: "offline" };
    }
}

// Render floating suggestion popup below the password input field
function showSuggestionPopup(passInput, userInput, data) {
    const existingPopup = document.getElementById("spmanager-popup");
    if (existingPopup) existingPopup.remove();

    const rect = passInput.getBoundingClientRect();
    const popup = document.createElement("div");
    popup.id = "spmanager-popup";
    popup.style.cssText = `
        position: fixed; top: ${rect.bottom + 6}px; left: ${rect.left}px;
        background: #1e272e; color: #ffffff; padding: 12px; border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4); z-index: 999999;
        font-family: 'Segoe UI', sans-serif; font-size: 13px; border: 1px solid #3498db;
    `;

    if (data.found) {
        popup.innerHTML = `
            <div style="margin-bottom:6px; color:#2ecc71; font-weight:bold;">🛡️ SPManager: Account found</div>
            <button id="spm-fill-btn" style="background:#3498db; color:#fff; border:none; padding:6px 12px; border-radius:4px; cursor:pointer; width:100%;">
                Autofill (${data.credentials.username})
            </button>
        `;
    } else {
        popup.innerHTML = `
            <div style="margin-bottom:6px; color:#f1c40f; font-weight:bold;">🛡️ SPManager: Strong password suggestion</div>
            <div style="font-family:monospace; background:#2f3640; padding:4px 8px; border-radius:4px; margin-bottom:8px;">${data.suggested}</div>
            <button id="spm-use-btn" style="background:#2ecc71; color:#fff; border:none; padding:6px 12px; border-radius:4px; cursor:pointer; width:100%; font-weight:bold;">
                Use & Save to Vault
            </button>
        `;
    }

    document.body.appendChild(popup);

    // Handle "Fill saved credentials" click
    const fillBtn = document.getElementById("spm-fill-btn");
    if (fillBtn) {
        fillBtn.addEventListener("click", () => {
            if (userInput) userInput.value = data.credentials.username;
            passInput.value = data.credentials.password;
            usedSuggestedPassword = true;
            popup.remove();
        });
    }

    // Handle "Use and save generated password" click
    const useBtn = document.getElementById("spm-use-btn");
    if (useBtn) {
        useBtn.addEventListener("click", async () => {
            passInput.value = data.suggested;
            usedSuggestedPassword = true;
            const usernameVal = userInput ? userInput.value : "User";
            await callVault({
                action: "save_credentials",
                domain: currentDomain,
                username: usernameVal || "User",
                password: data.suggested
            });
            popup.remove();
        });
    }
}

// Display prompt bar asking whether to save manually entered password
function askToSaveBar(username, password) {
    if (document.getElementById("spmanager-save-bar")) return;

    const bar = document.createElement("div");
    bar.id = "spmanager-save-bar";
    bar.style.cssText = `
        position: fixed; top: 15px; right: 15px; background: #1e272e; color: white;
        padding: 16px 20px; border-radius: 10px; z-index: 9999999;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-left: 5px solid #e67e22;
        font-family: 'Segoe UI', sans-serif; font-size: 14px;
    `;
    bar.innerHTML = `
        <div style="font-weight:bold; margin-bottom:8px;">🛡️ SPManager: Save password for ${currentDomain}?</div>
        <div style="font-size:12px; color:#aaa; margin-bottom:12px;">Manually entered password detected. Encrypt in vault?</div>
        <div style="display:flex; gap:10px;">
            <button id="spm-save-yes" style="background:#2ecc71; color:#fff; border:none; padding:6px 14px; border-radius:5px; cursor:pointer; font-weight:bold;">Save Password</button>
            <button id="spm-save-no" style="background:#7f8c8d; color:#fff; border:none; padding:6px 14px; border-radius:5px; cursor:pointer;">Ignore</button>
        </div>
    `;
    document.body.appendChild(bar);

    document.getElementById("spm-save-yes").onclick = async () => {
        await callVault({
            action: "save_credentials",
            domain: currentDomain,
            username: username || "User",
            password: password
        });
        bar.remove();
    };
    document.getElementById("spm-save-no").onclick = () => bar.remove();
}

// Scan the DOM for password input fields
function scanPage() {
    const passInputs = document.querySelectorAll('input[type="password"]');
    passInputs.forEach(passInput => {
        if (passInput.dataset.spmanagerScanned) return;
        passInput.dataset.spmanagerScanned = "true";

        const userInput = findUsernameInput(passInput);

        // Trigger suggestion popup when user focuses on the password field
        passInput.addEventListener("focus", async () => {
            usedSuggestedPassword = false;
            const res = await callVault({ action: "check_or_suggest", domain: currentDomain });
            if (res.status === "ok") {
                showSuggestionPopup(passInput, userInput, res);
            }
        });

        // Prompt to save if user ignored suggestions and submitted a manual password
        const handleManualEntry = () => {
            setTimeout(() => {
                const popup = document.getElementById("spmanager-popup");
                if (popup) popup.remove();

                if (!usedSuggestedPassword && passInput.value.length >= 4) {
                    const uVal = userInput ? userInput.value : "User";
                    askToSaveBar(uVal, passInput.value);
                }
            }, 250);
        };

        const form = passInput.closest("form");
        if (form) {
            form.addEventListener("submit", handleManualEntry);
        }
        passInput.addEventListener("change", handleManualEntry);
    });
}

// Run initial scan and observe DOM mutations for dynamic pages (SPAs / React)
scanPage();
const observer = new MutationObserver(scanPage);
observer.observe(document.body, { childList: true, subtree: true });