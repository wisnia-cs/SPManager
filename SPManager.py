import os
import sys
import json
import stat
import base64
import secrets
import string
import platform
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import customtkinter as ctk
from tkinter import messagebox
import pyperclip
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet, InvalidToken

# ==========================================
# 1. CRYPTOGRAPHY & FILE HIDING MODULE
# ==========================================

class SecureStorage:
    def __init__(self):
        self.os_type = platform.system()
        self.vault_dir = self._get_hidden_dir()
        self.vault_file = os.path.join(self.vault_dir, ".vault_data.enc")
        self.fernet = None
        self.data = {}  # { "domain.com": {"username": "...", "password": "..."} }

    def _get_hidden_dir(self):
        """Returns an OS-specific hidden directory path (Windows/Linux/macOS)."""
        if self.os_type == "Windows":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
            path = os.path.join(base, ".sys_sec_vault")
        elif self.os_type == "Darwin":  # macOS
            path = os.path.expanduser("~/Library/Application Support/.sys_sec_vault")
        else:  # Linux
            path = os.path.expanduser("~/.local/share/.sys_sec_vault")
        
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            self._hide_element(path)
        return path

    def _hide_element(self, path):
        """Applies hidden and system file attributes depending on the OS."""
        try:
            if self.os_type == "Windows":
                import ctypes
                # 0x02 = HIDDEN, 0x04 = SYSTEM (hidden as an OS protected system file)
                ctypes.windll.kernel32.SetFileAttributesW(path, 0x02 | 0x04)
            elif self.os_type == "Darwin":
                subprocess.run(["chflags", "hidden", path], check=False)
        except Exception:
            pass

    def _set_writable(self, writable=True):
        """Toggles read-only protection to prevent accidental deletion or modification."""
        if not os.path.exists(self.vault_file):
            return
        try:
            if writable:
                if self.os_type == "Windows":
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(self.vault_file, 0x80)  # NORMAL
                os.chmod(self.vault_file, stat.S_IWRITE | stat.S_IREAD)
            else:
                os.chmod(self.vault_file, stat.S_IREAD)  # Read-only (chmod 400)
                self._hide_element(self.vault_file)
        except Exception:
            pass

    def _derive_key(self, master_password: str, salt: bytes) -> bytes:
        """Derives an AES-256 key from the master password (PBKDF2, 600,000 iterations)."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(master_password.encode('utf-8')))

    def is_initialized(self) -> bool:
        return os.path.exists(self.vault_file)

    def unlock(self, master_password: str) -> bool:
        """Decrypts the vault or initializes a new one on first launch."""
        if not self.is_initialized():
            self.salt = os.urandom(16)
            key = self._derive_key(master_password, self.salt)
            self.fernet = Fernet(key)
            self.data = {}
            self.save()
            return True

        try:
            with open(self.vault_file, "rb") as f:
                raw = f.read()
            self.salt = raw[:16]
            encrypted_payload = raw[16:]
            key = self._derive_key(master_password, self.salt)
            self.fernet = Fernet(key)
            decrypted = self.fernet.decrypt(encrypted_payload)
            self.data = json.loads(decrypted.decode('utf-8'))
            return True
        except (InvalidToken, Exception):
            return False

    def save(self):
        """Encrypts vault data and re-applies file protection on disk."""
        if not self.fernet:
            return
        self._set_writable(True)
        payload = json.dumps(self.data).encode('utf-8')
        encrypted = self.fernet.encrypt(payload)
        with open(self.vault_file, "wb") as f:
            f.write(self.salt + encrypted)
        self._set_writable(False)

    @staticmethod
    def generate_password(length=18) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        while True:
            pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
                    and any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*()-_=+" for c in pwd)):
                return pwd


# ==========================================
# 2. LOCALHOST BRIDGE FOR BROWSER (PORT 50505)
# ==========================================

class BrowserBridgeHandler(BaseHTTPRequestHandler):
    storage_ref = None
    app_ref = None

    def log_message(self, format, *args):
        pass  # Suppress HTTP server logs in console

    def _send_cors_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._send_cors_headers()

    def do_POST(self):
        self._send_cors_headers()
        if not self.storage_ref or not self.storage_ref.fernet:
            self.wfile.write(json.dumps({"status": "locked"}).encode())
            return

        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length).decode('utf-8'))
        action = body.get("action")
        domain = body.get("domain", "")

        # 1. Browser checks for existing credentials or requests a generated password
        if action == "check_or_suggest":
            existing = self.storage_ref.data.get(domain)
            suggested = self.storage_ref.generate_password(18)
            self.wfile.write(json.dumps({
                "status": "ok",
                "found": bool(existing),
                "credentials": existing,
                "suggested": suggested
            }).encode())

        # 2. Browser sends new credentials to be encrypted and saved
        elif action == "save_credentials":
            username = body.get("username", "User")
            password = body.get("password", "")
            if domain and password:
                self.storage_ref.data[domain] = {"username": username, "password": password}
                self.storage_ref.save()
                if self.app_ref:
                    self.app_ref.after(0, self.app_ref.refresh_list)
            self.wfile.write(json.dumps({"status": "saved"}).encode())


# ==========================================
# 3. GRAPHICAL USER INTERFACE (CustomTkinter)
# ==========================================

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class PasswordManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SPManager")
        self.geometry("780x520")
        self.resizable(False, False)

        self.storage = SecureStorage()
        BrowserBridgeHandler.storage_ref = self.storage
        BrowserBridgeHandler.app_ref = self

        # Start local background bridge for browser extension
        self.server_thread = threading.Thread(target=self._start_bridge, daemon=True)
        self.server_thread.start()

        self._build_login_screen()

    def _start_bridge(self):
        server = HTTPServer(('127.0.0.1', 50505), BrowserBridgeHandler)
        server.serve_forever()

    def _build_login_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self, width=400, height=320, corner_radius=15)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        is_new = not self.storage.is_initialized()
        title_txt = "Create AES-256 Vault" if is_new else "Unlock Vault"
        sub_txt = "Set Master Password (cannot be recovered!):" if is_new else "Enter Master Password:"

        ctk.CTkLabel(frame, text="🔒 " + title_txt, font=("Segoe UI", 22, "bold")).pack(pady=(35, 10))
        ctk.CTkLabel(frame, text=sub_txt, font=("Segoe UI", 13), text_color="gray").pack(pady=(0, 15))

        self.master_Input = ctk.CTkEntry(frame, width=280, height=40, show="•", placeholder_text="Master Password...")
        self.master_Input.pack(pady=10)
        self.master_Input.bind("<Return>", lambda e: self._attempt_unlock())

        btn_txt = "Encrypt & Create" if is_new else "Decrypt Vault"
        ctk.CTkButton(frame, text=btn_txt, width=280, height=40, font=("Segoe UI", 14, "bold"),
                      command=self._attempt_unlock).pack(pady=15)

        ctk.CTkLabel(frame, text=f"Hidden path: {self.storage.vault_file}", font=("Consolas", 10), text_color="#666666").pack(pady=(10, 20), padx=20)

    def _attempt_unlock(self):
        pwd = self.master_Input.get()
        if len(pwd) < 4:
            messagebox.showwarning("Error", "Master password must be at least 4 characters long.")
            return
        if self.storage.unlock(pwd):
            self._build_main_screen()
        else:
            messagebox.showerror("Access Denied", "Invalid Master Password or corrupted vault file!")

    def _build_main_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=230, corner_radius=0)
        sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(sidebar, text="🛡️ SPManager", font=("Segoe UI", 20, "bold")).pack(pady=(25, 5))
        ctk.CTkLabel(sidebar, text="Browser Bridge: ACTIVE", font=("Segoe UI", 11), text_color="#2ecc71").pack(pady=(0, 25))

        ctk.CTkLabel(sidebar, text="Add Manually:", font=("Segoe UI", 13, "bold")).pack(padx=20, anchor="w")
        self.ent_domain = ctk.CTkEntry(sidebar, placeholder_text="Domain (e.g. github.com)", width=190)
        self.ent_domain.pack(pady=6, padx=20)

        self.ent_user = ctk.CTkEntry(sidebar, placeholder_text="Username / Email", width=190)
        self.ent_user.pack(pady=6, padx=20)

        self.ent_pass = ctk.CTkEntry(sidebar, placeholder_text="Password", width=190)
        self.ent_pass.pack(pady=6, padx=20)

        ctk.CTkButton(sidebar, text="🎲 Generate Strong Password", fg_color="#34495e", hover_color="#2c3e50", width=190,
                      command=self._fill_generated).pack(pady=6, padx=20)

        ctk.CTkButton(sidebar, text="💾 Save to Vault", width=190, command=self._add_manual).pack(pady=10, padx=20)

        # Main vault list area
        main_area = ctk.CTkFrame(self, fg_color="transparent")
        main_area.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        top_bar = ctk.CTkFrame(main_area, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(top_bar, text="Saved Accounts", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.status_lbl = ctk.CTkLabel(top_bar, text="", font=("Segoe UI", 12), text_color="#f39c12")
        self.status_lbl.pack(side="right")

        self.scroll_list = ctk.CTkScrollableFrame(main_area, height=400)
        self.scroll_list.pack(fill="both", expand=True)

        self.refresh_list()

    def _fill_generated(self):
        pwd = self.storage.generate_password(18)
        self.ent_pass.delete(0, 'end')
        self.ent_pass.insert(0, pwd)

    def _add_manual(self):
        d = self.ent_domain.get().strip()
        u = self.ent_user.get().strip()
        p = self.ent_pass.get().strip()
        if not d or not p:
            return
        self.storage.data[d] = {"username": u, "password": p}
        self.storage.save()
        self.ent_domain.delete(0, 'end')
        self.ent_user.delete(0, 'end')
        self.ent_pass.delete(0, 'end')
        self.refresh_list()

    def refresh_list(self):
        for w in self.scroll_list.winfo_children():
            w.destroy()

        if not self.storage.data:
            ctk.CTkLabel(self.scroll_list, text="No saved passwords yet. Log in via browser or add an entry manually.",
                         text_color="gray").pack(pady=40)
            return

        for domain, creds in self.storage.data.items():
            row = ctk.CTkFrame(self.scroll_list, corner_radius=8)
            row.pack(fill="x", pady=5, padx=5)

            info = f"🌐 {domain}   |   👤 {creds.get('username', '')}"
            ctk.CTkLabel(row, text=info, font=("Segoe UI", 13, "bold")).pack(side="left", padx=12, pady=10)

            ctk.CTkButton(row, text="Delete", width=60, fg_color="#c0392b", hover_color="#922b21",
                          command=lambda d=domain: self._delete_entry(d)).pack(side="right", padx=6)
            ctk.CTkButton(row, text="Copy Password (15s)", width=145,
                          command=lambda p=creds.get('password', ''): self._copy_with_timer(p)).pack(side="right", padx=6)

    def _copy_with_timer(self, pwd):
        pyperclip.copy(pwd)
        self.status_lbl.configure(text="📋 Copied! Clearing clipboard in 15s...")
        self.after(15000, self._clear_clipboard)

    def _clear_clipboard(self):
        pyperclip.copy("")
        self.status_lbl.configure(text="🧹 Clipboard cleared automatically.")

    def _delete_entry(self, domain):
        if domain in self.storage.data:
            del self.storage.data[domain]
            self.storage.save()
            self.refresh_list()

if __name__ == "__main__":
    app = PasswordManagerApp()
    app.mainloop()