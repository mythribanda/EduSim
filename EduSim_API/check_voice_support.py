import winreg

def list_installed_sapi_voices():
    print("=== WINDOWS SAPI5 & ONECORE LOCAL INSTALLED VOICES ===")
    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Speech\Voices\Tokens", "SAPI5 Local Voices"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens", "OneCore Modern Offline Voices"),
    ]
    
    for root, path, label in locations:
        print(f"\n--- {label} ---")
        try:
            with winreg.OpenKey(root, path) as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        try:
                            desc, _ = winreg.QueryValueEx(subkey, "")
                        except Exception:
                            desc = subkey_name
                        try:
                            lang, _ = winreg.QueryValueEx(subkey, "LangID")
                        except Exception:
                            lang = "N/A"
                        print(f"  * {desc} [Key: {subkey_name}] (LangID: {lang})")
        except FileNotFoundError:
            print(f"  Path not found: {path}")

if __name__ == "__main__":
    list_installed_sapi_voices()
