import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import os
import threading
import requests
import ipaddress
from dotenv import load_dotenv

from main import DNSAutomate

class DNSAutomateGUI(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("DNS Automate")
        self.geometry("920x520")
        self.resizable(False, False)

        self.env_path = Path(__file__).resolve().parent / ".env"
        self.backend = DNSAutomate()

        if not self._ensure_config():
            self.destroy()
            return

        self._build_main_ui()
        self._build_context_menu()
        self._load_dns_records_async()


    # ======================================================
    # CONFIG FLOW
    # ======================================================

    def _ensure_config(self) -> bool:
        if self._load_config():
            return True
        return self._open_config_window(force=True)

    def _load_config(self) -> bool:
        if not self.env_path.exists():
            return False

        load_dotenv(self.env_path)
        token = os.getenv("API_TOKEN")
        zone = os.getenv("ZONE_ID")

        if not token or not zone:
            return False

        self.backend._API_TOKEN = token
        self.backend._ZONE_ID = zone
        return True

    def _save_config(self, token: str, zone: str):
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write(f"API_TOKEN={token}\n")
            f.write(f"ZONE_ID={zone}\n")

        self.backend._API_TOKEN = token
        self.backend._ZONE_ID = zone

    # ======================================================
    # MAIN UI
    # ======================================================

    def _build_main_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Button(top, text="Novo", command=self._new_record).pack(side="left")
        ttk.Button(top, text="Editar", command=self._edit_record).pack(side="left", padx=5)
        ttk.Button(top, text="Configurações", command=self._open_config_window).pack(side="left", padx=5)

        self.table = ttk.Treeview(
            self,
            columns=("name", "type", "content", "proxied", "id"),
            show="headings"
        )

        for col, text in [
            ("name", "Nome"),
            ("type", "Tipo"),
            ("content", "Conteúdo"),
            ("proxied", "Proxied"),
            ("id", "ID")
        ]:
            self.table.heading(col, text=text)

        self.table.column("id", width=0, stretch=False)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)
        self.table.bind("<Button-3>", self._open_context_menu)

    def _build_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Excluir", command=self._delete_selected_record)
        self.context_menu.add_command(label="Editar", command=self._edit_record)

    # ======================================================
    # LOADING MODAL
    # ======================================================

    def _show_loading(self, text="Carregando e obtendo dados..."):
        if hasattr(self, "loading") and self.loading.winfo_exists():
            return  # JÁ EXISTE, NÃO CRIA OUTRO

        self.loading = tk.Toplevel(self)
        self.loading.title("Aguarde")
        self.loading.geometry("360x120")
        self.loading.resizable(False, False)
        self.loading.transient(self)
        self.loading.grab_set()
        self.loading.focus_force()
        self.loading.protocol("WM_DELETE_WINDOW", lambda: None)  # bloqueia X

        ttk.Label(
            self.loading,
            text=text,
            font=("Segoe UI", 10, "bold")
        ).pack(expand=True, pady=30)

        self.loading.update_idletasks()


    def _hide_loading(self):
        if hasattr(self, "loading") and self.loading.winfo_exists():
            try:
                self.loading.grab_release()
                self.loading.destroy()
            except tk.TclError:
                pass

    # ======================================================
    # DATA
    # ======================================================

    def _load_dns_records_async(self):
        if not self.backend._ZONE_ID:
            return

        if not self.backend._ZONE_NAME:
            try:
                self.backend.load_zone_name()
            except Exception as e:
                messagebox.showerror("Erro", str(e))
                return

        self._show_loading()
        threading.Thread(target=self._load_dns_records, daemon=True).start()


    def _load_dns_records(self):
        try:
            url = f"https://api.cloudflare.com/client/v4/zones/{self.backend._ZONE_ID}/dns_records"
            r = requests.get(url, headers=self.backend._headers(), timeout=10)
            r.raise_for_status()
            self.after(0, self._populate_table, r.json()["result"])
        except Exception as e:
            self.after(0, messagebox.showerror, "Erro", str(e))
        finally:
            self.after(0, self._hide_loading)

    def _populate_table(self, records):
        self.table.delete(*self.table.get_children())

        records_sorted = sorted(records, key=lambda r: r["name"].lower())

        for r in records_sorted:
            prefix = self._extract_prefix(r["name"])

            self.table.insert(
                "",
                "end",
                values=(
                    prefix,
                    r["type"],
                    r["content"],
                    r.get("proxied", False),
                    r["id"]
                )
            )

    def _extract_prefix(self, full_name: str) -> str:
        zone = self.backend._ZONE_NAME

        if not zone:
            return full_name

        zone = zone.lower()
        full_name = full_name.lower()

        if full_name == zone:
            return "@"

        if full_name.endswith("." + zone):
            return full_name[: -(len(zone) + 1)]

        return full_name

    # ======================================================
    # ACTIONS (NOVO / DELETE)
    # ======================================================

    def _new_record(self):
        win = tk.Toplevel(self)
        win.title("Novo Registro DNS")
        win.geometry("620x180")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        win.focus_force()

        for i in range(4):
            win.columnconfigure(i, weight=1)

        ttk.Label(win, text="Nome").grid(row=0, column=0, sticky="e", padx=5, pady=10)
        name_entry = ttk.Entry(win, width=30)
        name_entry.grid(row=0, column=1)

        ttk.Label(win, text="Conteúdo").grid(row=0, column=2, sticky="e", padx=5)
        content_entry = ttk.Entry(win, width=30)
        content_entry.grid(row=0, column=3)

        ttk.Label(win, text="Tipo").grid(row=1, column=0, sticky="e", padx=5)
        type_combo = ttk.Combobox(
            win,
            values=["AUTO", "A", "AAAA", "CNAME", "TXT"],
            state="readonly",
            width=27
        )
        type_combo.set("AUTO")
        type_combo.grid(row=1, column=1)

        proxied_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Proxied", variable=proxied_var)\
            .grid(row=1, column=2, columnspan=2, sticky="w")

        def save():
            name = name_entry.get().strip()
            content = content_entry.get().strip()
            rtype = type_combo.get()

            if not name or not content:
                messagebox.showerror("Erro", "Preencha todos os campos")
                return

            if rtype == "AUTO":
                try:
                    ipaddress.ip_address(content)
                    rtype = "A"
                except ValueError:
                    rtype = "CNAME"

            self._show_loading("Criando registro DNS...")

            try:
                url = f"https://api.cloudflare.com/client/v4/zones/{self.backend._ZONE_ID}/dns_records"
                requests.post(
                    url,
                    json={
                        "type": rtype,
                        "name": name,
                        "content": content,
                        "ttl": 1,
                        "proxied": proxied_var.get()
                    },
                    headers=self.backend._headers(),
                    timeout=10
                ).raise_for_status()
                win.destroy()
                self._load_dns_records_async()
            except Exception as e:
                messagebox.showerror("Erro", str(e))
            finally:
                self._hide_loading()

        ttk.Button(win, text="Salvar", command=save)\
            .grid(row=2, column=0, columnspan=4, pady=20)

    def _delete_selected_record(self):
        selected = self.table.selection()
        if not selected:
            return

        rtype, name, content, proxied, rid = self.table.item(selected[0], "values")

        if not messagebox.askyesno(
            "Confirmar exclusão",
            f"Tipo: {rtype}\nNome: {name}\nConteúdo: {content}\nProxied: {proxied}"
        ):
            return

        self._show_loading("Excluindo registro DNS...")

        def worker():
            try:
                url = f"https://api.cloudflare.com/client/v4/zones/{self.backend._ZONE_ID}/dns_records/{rid}"
                requests.delete(url, headers=self.backend._headers(), timeout=10).raise_for_status()
                self.after(0, self._load_dns_records_async)
            except Exception as e:
                self.after(0, messagebox.showerror, "Erro", str(e))
            finally:
                self.after(0, self._hide_loading)

        threading.Thread(target=worker, daemon=True).start()


    def _edit_record(self):
        messagebox.showinfo("Editar", "Funcionalidade será implementada futuramente.")

    def _open_context_menu(self, event):
        row = self.table.identify_row(event.y)
        if row:
            self.table.selection_set(row)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    # ======================================================
    # CONFIG WINDOW
    # ======================================================

    def _open_config_window(self, force=False) -> bool:
        win = tk.Toplevel(self)
        win.title("Configurações")
        win.geometry("370x120")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        win.update_idletasks()
        win.lift()
        win.focus_force()
        win.focus_force()

        ttk.Label(win, text="API Token").grid(row=0, column=0, sticky="e", padx=10, pady=10)
        token_entry = ttk.Entry(win, width=45)
        token_entry.grid(row=0, column=1)

        ttk.Label(win, text="Zone ID").grid(row=1, column=0, sticky="e", padx=10)
        zone_entry = ttk.Entry(win, width=45)
        zone_entry.grid(row=1, column=1)

        token_entry.insert(0, self.backend._API_TOKEN or "")
        zone_entry.insert(0, self.backend._ZONE_ID or "")

        result = {"ok": False}

        def save():
            token = token_entry.get().strip()
            zone = zone_entry.get().strip()

            if not token or not zone:
                messagebox.showerror("Erro", "Preencha todos os campos")
                return

            self._save_config(token, zone)
            result["ok"] = True
            win.destroy()
            self.backend.set_zone(zone, None)
            self._load_dns_records_async()


        ttk.Button(win, text="Salvar", command=save).grid(row=2, column=0, columnspan=2, pady=20)
        self.wait_window(win)
        return result["ok"]


if __name__ == "__main__":
    DNSAutomateGUI().mainloop()



