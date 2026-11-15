# 🛡️ SPManager — Cross-Platform Local AES-256 Password Manager

A lightweight, cross-platform (**Windows / Linux / macOS**) local desktop password manager featuring an **AES-256** encrypted vault and a companion browser extension that scans login forms, suggests strong passwords, and saves credentials automatically.

---

## ✨ Key Features

* **Strong Local Cryptography:** Encrypts all stored credentials using **AES-256 (Fernet)** with a key derived via **PBKDF2-HMAC-SHA256** (600,000 iterations) and a unique 16-byte cryptographic salt. Your Master Password is never stored on disk or transmitted over the network.
* **OS-Level Vault Protection:** Automatically stores the encrypted database in deep system directories and applies native OS protections (`HIDDEN` + `SYSTEM` attributes on Windows, `chmod 400` read-only permissions on Linux/macOS) to prevent accidental deletion or tampering.
* **Smart Browser Scanner (Extension):** Detects `<input type="password">` fields across websites, offers one-click autofill or cryptographically generated passwords (`secrets` module), and prompts to save manually entered credentials.
* **Auto-Clearing Clipboard:** Automatically wipes copied passwords from the system clipboard after 15 seconds to prevent accidental leaks.
* **Isolated Localhost Bridge:** Communicates strictly locally between the browser extension and desktop vault via `127.0.0.1:50505` with zero external cloud dependencies.

---

## 🏗️ Architecture Overview

1. **Desktop Vault (`SPManager`):** Built with Python and `CustomTkinter`. Handles key derivation in RAM, AES-256 encryption/decryption, file attribute hardening, and serves a local HTTP bridge on `127.0.0.1:50505`.
2. **Browser Extension (`Manifest V3`):** Injects a lightweight content script (`scanner.js`) that monitors DOM mutations for login/registration forms, queries the local vault for saved accounts, and handles password generation or capture.

---

## 🚀 Quick Start (From Source)

1. **Clone the repository:**

```bash
git clone [https://github.com/wisnia-cs/SPManager.git](https://github.com/wisnia-cs/SPManager.git)
cd SPManager
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Run the desktop application:**

```bash
python vault_app.py
```

*(Replace `vault_app.py` with your main script filename if renamed).*

---

## 🧩 Installing the Browser Extension

Works on all Chromium-based browsers (**Chrome, Edge, Brave, Opera, Vivaldi**):

1. Open your browser and navigate to `chrome://extensions/`.
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the extension folder (`extension/`) from this repository.
4. Keep **SPManager** unlocked in the background while browsing.

---

## 📦 Building Standalone Executable (`.exe` / Binary)

To package the desktop application into a single standalone executable using **PyInstaller**:

```bash
pip install pyinstaller
python -m PyInstaller --noconsole --onefile --collect-all customtkinter --name "SPManager" vault_app.py
```

The compiled binary will be generated inside the `dist/` folder.
