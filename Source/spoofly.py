import customtkinter as ctk
import ctypes
import random
import re
import subprocess
import time
import wmi
import winreg
import threading
import sys
from tkinter import messagebox

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

REGISTRY_PATH = (
    r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
)


def is_admin():
    return ctypes.windll.shell32.IsUserAnAdmin()


def generate_mac():
    mac = [
        0x02,
        random.randint(0x00, 0x7F),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
    ]
    return "".join(f"{b:02X}" for b in mac)


def clean_mac(mac_str):
    return re.sub(r"[^0-9A-Fa-f]", "", mac_str).upper()


def is_valid_mac(mac_str):
    clean = clean_mac(mac_str)
    return bool(re.fullmatch(r"[0-9A-F]{12}", clean))


def is_zero_mac(mac_str):
    return clean_mac(mac_str) == "000000000000"


def get_interfaces():
    w = wmi.WMI()
    return [
        (
            adapter.NetConnectionID,
            adapter.MACAddress or "N/A",
            adapter.PNPDeviceID,
            adapter.GUID,
        )
        for adapter in w.Win32_NetworkAdapter()
        if adapter.PhysicalAdapter and adapter.NetConnectionID
    ]


def set_mac_address(guid, new_mac):
    i = 0
    while True:
        subkey = f"{i:04}"
        full_path = f"{REGISTRY_PATH}\\{subkey}"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, full_path, 0, winreg.KEY_ALL_ACCESS
            )
        except (FileNotFoundError, PermissionError, OSError):
            break
        try:
            val, _ = winreg.QueryValueEx(key, "NetCfgInstanceId")
            if val.lower() == guid.lower():
                winreg.SetValueEx(key, "NetworkAddress", 0, winreg.REG_SZ, new_mac)
                return True
        except FileNotFoundError:
            pass
        i += 1
    return False


def reset_mac_address(guid):
    i = 0
    while True:
        subkey = f"{i:04}"
        full_path = f"{REGISTRY_PATH}\\{subkey}"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, full_path, 0, winreg.KEY_ALL_ACCESS
            )
        except (FileNotFoundError, PermissionError, OSError):
            break
        try:
            val, _ = winreg.QueryValueEx(key, "NetCfgInstanceId")
            if val.lower() == guid.lower():
                try:
                    winreg.DeleteValue(key, "NetworkAddress")
                    return True
                except FileNotFoundError:
                    return True
        except FileNotFoundError:
            pass
        i += 1
    return False


def restart_interface(name):
    subprocess.run(
        ["netsh", "interface", "set", "interface", name, "admin=disable"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    subprocess.run(
        ["netsh", "interface", "set", "interface", name, "admin=enable"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)


class MacChangerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows MAC Address Changer - 0xDevSh3ll")
        self.root.geometry("550x500")
        self.root.resizable(False, False)

        self.interfaces = get_interfaces()
        self.selected_interface_str = ctk.StringVar()
        self.selected_interface_data = None
        self.mac_input = ctk.StringVar()

        self.build_ui()

    def build_ui(self):
        ctk.CTkLabel(
            self.root, text="Select Network Interface:", font=ctk.CTkFont(size=16)
        ).pack(pady=(20, 10))

        self.interface_button = ctk.CTkButton(
            self.root,
            textvariable=self.selected_interface_str,
            command=self.open_interface_selector,
            width=450,
        )
        self.interface_button.pack()

        ctk.CTkButton(
            self.root, text="Reload Interfaces", command=self.reload_interfaces
        ).pack(pady=(10, 15))

        ctk.CTkLabel(
            self.root,
            text="Enter MAC Address (or click Generate):",
            font=ctk.CTkFont(size=16),
        ).pack(pady=(10, 5))
        ctk.CTkEntry(self.root, textvariable=self.mac_input, width=300).pack()

        self.button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.button_frame.pack(pady=15)

        self.btn_generate = ctk.CTkButton(
            self.button_frame, text="Generate Random", command=self.generate_random_mac
        )
        self.btn_generate.pack(side="left", padx=5)

        self.btn_apply = ctk.CTkButton(
            self.button_frame, text="Apply", command=self.apply_mac
        )
        self.btn_apply.pack(side="left", padx=5)

        self.btn_reset = ctk.CTkButton(
            self.button_frame, text="Reset", command=self.reset_mac
        )
        self.btn_reset.pack(side="left", padx=5)

        ctk.CTkLabel(
            self.root, text="Command Line Debugging :", font=ctk.CTkFont(size=16)
        ).pack(pady=(15, 5))
        self.log_box = ctk.CTkTextbox(self.root, height=180, width=520)
        self.log_box.pack()
        self.log_box.configure(state="disabled")

        self.reload_interfaces(init=True)

    def set_buttons_state(self, state):
        for btn in [self.btn_generate, self.btn_apply, self.btn_reset]:
            btn.configure(state=state)

    def log(self, msg, success=True):
        self.log_box.configure(state="normal")
        prefix = "[+] " if success else "[-] "
        self.log_box.insert("end", f"{prefix}{msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def generate_random_mac(self):
        self.mac_input.set(generate_mac())
        self.log("Generated random MAC address.")

    def open_interface_selector(self):
        if not self.interfaces:
            self.log("No interfaces available to select.", success=False)
            return
        popup = ctk.CTkToplevel(self.root)
        popup.iconbitmap("icon.ico")
        popup.title("Network Interfaces List :")
        popup.geometry("400x300")
        popup.grab_set()

        frame = ctk.CTkScrollableFrame(popup, width=380, height=260)
        frame.pack(padx=10, pady=10, fill="both", expand=True)

        for name, mac, _, guid in self.interfaces:
            display = f"{name} ({mac})"
            btn = ctk.CTkButton(
                frame,
                text=display,
                anchor="w",
                width=360,
                command=lambda n=name, m=mac, g=guid: self.select_interface(
                    n, m, g, popup
                ),
            )
            btn.pack(pady=5, padx=5)

    def select_interface(self, name, mac, guid, popup):
        display = f"{name} ({mac})"
        self.selected_interface_str.set(display)
        self.selected_interface_data = (name, mac, guid)
        self.mac_input.set(clean_mac(mac or ""))
        if popup:
            popup.destroy()

    def apply_mac(self):
        if not self.selected_interface_data:
            messagebox.showerror("Error", "Please select an interface.")
            return
        name, current_mac, guid = self.selected_interface_data
        new_mac = clean_mac(self.mac_input.get())

        if not is_valid_mac(new_mac):
            self.log("Invalid MAC address format.", success=False)
            return
        if is_zero_mac(new_mac):
            self.log("MAC address cannot be all zeros.", success=False)
            return
        if clean_mac(current_mac or "") == new_mac:
            self.log(
                "The entered MAC address is already the current MAC.", success=False
            )
            return
        self.log(f"Applying MAC: {new_mac} to {name}")
        self.set_buttons_state("disabled")
        threading.Thread(
            target=self._apply_thread, args=(name, guid, new_mac), daemon=True
        ).start()

    def _apply_thread(self, name, guid, new_mac):
        if set_mac_address(guid, new_mac):
            self.log("MAC address changed successfully.")
            self.log("Restarting interface...")
            restart_interface(name)
            self.log("Interface restarted.")
        else:
            self.log("Failed to change MAC address.", success=False)
        self.set_buttons_state("normal")

    def reset_mac(self):
        if not self.selected_interface_data:
            messagebox.showerror("Error", "Please select an interface.")
            return
        name, _, guid = self.selected_interface_data
        self.log(f"Resetting MAC for {name}...")
        self.set_buttons_state("disabled")
        threading.Thread(
            target=self._reset_thread, args=(name, guid), daemon=True
        ).start()

    def _reset_thread(self, name, guid):
        if reset_mac_address(guid):
            self.log("MAC address reset to hardware default.")
            self.log("Restarting interface...")
            restart_interface(name)
            self.log("Interface restarted.")
        else:
            self.log("Failed to reset MAC address.", success=False)
        self.set_buttons_state("normal")

    def reload_interfaces(self, init=False):
        self.interfaces = get_interfaces()
        if self.interfaces:
            first = self.interfaces[0]
            self.select_interface(first[0], first[1], first[3], popup=None)
            if not init:
                self.log("Interface list reloaded.")
        else:
            self.selected_interface_str.set("No interfaces found")
            self.selected_interface_data = None
            self.mac_input.set("")
            self.log("No interfaces found.", success=False)


if __name__ == "__main__":
    if not is_admin():
        messagebox.showerror(
            "Permission Denied", "Please run this script as Administrator."
        )
        sys.exit(1)
    root = ctk.CTk()
    root.iconbitmap("icon.ico")
    app = MacChangerGUI(root)
    root.mainloop()


#============================#
#                            #
#          (    )            #
#         ( (__) )  Boo!     #
#        ( >____% )          #
#━━━━━━━━━^^━━━━^^━━━━━━━━━━━#
# - Windows Mac Changer v1.0 #
#                            #
#      ~~0xDevSh3ll~~        #
#============================#