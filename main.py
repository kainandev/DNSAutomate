import requests
import os
import ipaddress
from pathlib import Path
from dotenv import load_dotenv

# +==============================================================================+
# |                                                                              |
# |  ____   _   _  ____       _           _                            _         |
# | |  _ \ | \ | |/ ___|     / \   _   _ | |_  ___   _ __ ___    __ _ | |_  ___  |
# | | | | ||  \| |\___ \    / _ \ | | | || __|/ _ \ | '_ ` _ \  / _` || __|/ _ \ |
# | | |_| || |\  | ___) |  / ___ \| |_| || |_| (_) || | | | | || (_| || |_|  __/ |
# | |____/ |_| \_||____/  /_/   \_\\__,_| \__|\___/ |_| |_| |_| \__,_| \__|\___| |
# |   ____  _                    _   __  _                                       |
# |  / ___|| |  ___   _   _   __| | / _|| |  __ _  _ __  ___                     |
# | | |    | | / _ \ | | | | / _` || |_ | | / _` || '__|/ _ \                    |
# | | |___ | || (_) || |_| || (_| ||  _|| || (_| || |  |  __/                    |
# |  \____||_| \___/  \__,_| \__,_||_|  |_| \__,_||_|   \___|                    |
# |                                                                              |
# +==============================================================================+
class DNSAutomate:

    def __init__(self, CLODFLARE_API="https://api.cloudflare.com/client/v4/zones/"):
        self.env_path = Path(__file__).resolve().parent / '.env'
        self._API_TOKEN = None
        self._ZONE_ID = None
        self._ZONE_NAME = None
        self.CLODFLARE_API = CLODFLARE_API

    # =========================
    # CONFIGURAÇÃO EM .ENV
    # =========================

    def load_config(self) -> bool:
        if self.env_path.is_file():
            load_dotenv(self.env_path)
            self._API_TOKEN = os.getenv('API_TOKEN')
            self._ZONE_ID = os.getenv('ZONE_ID')
            return bool(self._API_TOKEN and self._ZONE_ID)
        return False

    def create_config(self, token: str, zone: str) -> bool:
        with open(self.env_path, 'w', encoding='utf-8') as f:
            f.write(f"API_TOKEN={token}\nZONE_ID={zone}\n")
        return self.load_config()

    def set_zone(self, zone_id, zone_name):
        self._ZONE_ID = zone_id
        self._ZONE_NAME = zone_name

    # =========================
    # CLOUDFLARE
    # =========================

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._API_TOKEN}",
            "Content-Type": "application/json"
        }

    def select_zone(self):
        r = requests.get(
            self.CLODFLARE_API,
            headers=self._headers(),
            timeout=10
        )

        if not r.ok:
            self.pretty_error(r.json())
            return None

        zones = r.json()["result"]
        for i, z in enumerate(zones, 1):
            print(f"[{i}] {z['name']}")

        try:
            return zones[int(input("Selecione a zona: ")) - 1]["id"]
        except Exception:
            return None

    # =========================
    # DNS
    # =========================

    def detect_record_type(self, content: str):
        try:
            ip = ipaddress.ip_address(content)
            return "AAAA" if ip.version == 6 else "A", True
        except ValueError:
            return "CNAME", True

    def handle_register(self, command: str):
        parts = command.split()

        if len(parts) < 3:
            print("Uso: /register <prefix> <IP|HOST> [TYPE] [true|false]")
            return

        prefix = parts[1]
        content = parts[2]

        record_type, default_proxied = self.detect_record_type(content)

        if len(parts) >= 4:
            record_type = parts[3].upper()

        proxied = default_proxied
        if len(parts) >= 5:
            proxied = parts[4].lower() == "true"

        self.create_dns_record(prefix, content, record_type, proxied)

    def create_dns_record(self, name, content, rtype, proxied):
        url = f"{self.CLODFLARE_API + self._ZONE_ID}/dns_records"

        payload = {
            "type": rtype,
            "name": name,
            "content": content,
            "ttl": 1,
            "proxied": proxied
        }

        r = requests.post(url, json=payload, headers=self._headers(), timeout=10)

        if r.ok:
            print("\nRegistro criado com sucesso")
            print(f"- Nome    : {name}")
            print(f"- Tipo    : {rtype}")
            print(f"- Conteúdo: {content}")
            print(f"- Proxied : {proxied}\n")
        else:
            self.pretty_error(r.json())


    def list_dns_record(self):
        url = f"{self.CLODFLARE_API + self._ZONE_ID}/dns_records"
        r = requests.get(url, headers=self._headers(), timeout=10)

        if not r.ok:
            self.pretty_error(r.json())
            return

        records = r.json()["result"]
        return records

    def delete_dns_record(self):
        records = self.list_dns_record()

        for i, rec in enumerate(records, 1):
            print(f"[{i}] {rec['type']} {rec['name']} → {rec['content']}")

        try:
            rid = records[int(input("Selecione: ")) - 1]["id"]
        except Exception:
            return

        d = requests.delete(f"{url}/{rid}", headers=self._headers(), timeout=10)

        if d.ok:
            print("Registro removido com sucesso.")
        else:
            self.pretty_error(d.json())

    def load_zone_name(self):
        url = self.CLODFLARE_API
        r = requests.get(url, headers=self._headers(), timeout=10)
        r.raise_for_status()

        for z in r.json()["result"]:
            if z["id"] == self._ZONE_ID:
                self._ZONE_NAME = z["name"]
                return

        raise RuntimeError("ZONE_ID não encontrado na conta")

    # =========================
    # ERROR
    # =========================

    def pretty_error(self, response):
        print("\nERRO NA API CLOUDFLARE")
        for err in response.get("errors", []):
            print(f"• Código : {err.get('code')}")
            print(f"• Motivo : {err.get('message')}")
        print()


# +=====================================================+
# |                                                     |
# |  _____                 _                _           |
# | |_   _|___  _ __ ___  (_) _ __    __ _ | |          |
# |   | | / _ \| '_ ` _ \ | || '_ \  / _` || |          |
# |   | ||  __/| | | | | || || | | || (_| || |          |
# |   |_| \___||_| |_| |_||_||_| |_| \__,_||_|          |
# |  ___         _                __                    |
# | |_ _| _ __  | |_  ___  _ __  / _|  __ _   ___  ___  |
# |  | | | '_ \ | __|/ _ \| '__|| |_  / _` | / __|/ _ \ |
# |  | | | | | || |_|  __/| |   |  _|| (_| || (__|  __/ |
# | |___||_| |_| \__|\___||_|   |_|   \__,_| \___|\___| |
# |                                                     |
# +=====================================================+
class TerminalInterface(DNSAutomate):

    def __init__(self, help_menu: list = []):
        super().__init__()
        self.help_menu = help_menu 

    def help_menu_terminal(self):
        largura = 100
        print("\n+ " + "=" * largura + " +")
        for cmd, desc in self.help_menu:
            print(f"| /{cmd:<45} | {desc:<45}")
        print("+ " + "=" * largura + " +")

    def start_terminal(self):
        if not self.load_config():
            token = input("API Token : ").strip()
            self._API_TOKEN = token
            zone = self.select_zone()
            if not zone:
                return
            self.create_config(token, zone)

        self.main_loop()

    def main_loop(self):
        while True:
            self.help_menu_terminal()
            cmd = input("==> ").strip()

            if cmd == "/exit":
                print("Bye :)")
                break

            elif cmd.startswith("/register"):
                self.handle_register(cmd)

            elif cmd == "/delete":
                self.delete_dns_record()

            elif cmd == "/list":
                records = self.list_dns_record()

                for i, rec in enumerate(records, 1):
                    print(f"[{i}] {rec['type']} {rec['name']} → {rec['content']}")

            else:
                print("Comando inválido.")

if __name__ == "__main__":

    menu = [
        ["exit", "Sai do programa"],
        ["register <prefix> <IP> [TYPE] [true|false]", "Registra um novo DNS"],
        ["delete", "Remove um DNS existente"],
        ["list", "Lista todos os registros."]
    ]

    app = TerminalInterface(help_menu=menu)
    app.start_terminal()