import os
import re
import time
import keyboard
import winreg
import argostranslate.package
import argostranslate.translate

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
ENV_DATA = {}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            ENV_DATA[key.strip()] = val.strip()

def get_env_bool(key: str, default: bool) -> bool:
    val = ENV_DATA.get(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")

MY_NICKNAME = ENV_DATA.get("MY_NICKNAME", "p0d$0lnyh")
CSGO_DIR = ENV_DATA.get("CSGO_DIR", r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo")
TRIGGER_KEY = ENV_DATA.get("TRIGGER_KEY", "f8")
AUTO_STEAM_NICK = get_env_bool("AUTO_STEAM_NICK", True)
DEFAULT_ACTIVE = get_env_bool("DEFAULT_ACTIVE", True)

LOG_PATH = os.path.join(CSGO_DIR, "console.log")
CFG_PATH = os.path.join(CSGO_DIR, "cfg", "translate.cfg")
DICT_PATH = os.path.join(os.path.dirname(__file__), "dictionary.txt")

is_active = DEFAULT_ACTIVE
CS_SLANG = {}

def get_steam_nickname() -> str:
    if not AUTO_STEAM_NICK:
        return MY_NICKNAME
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        
        userdata_path = os.path.join(steam_path, "userdata")
        if not os.path.exists(userdata_path):
            return MY_NICKNAME

        for user_id in os.listdir(userdata_path):
            config_file = os.path.join(userdata_path, user_id, "config", "localconfig.vdf")
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    match = re.search(r'"PersonaName"\s+"([^"]+)"', content, re.IGNORECASE)
                    if match:
                        return match.group(1)
    except Exception:
        pass
    return MY_NICKNAME

def load_dictionary():
    new_dict = {}
    if not os.path.exists(DICT_PATH):
        return new_dict
    
    with open(DICT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            pattern, replacement = line.split("=", 1)
            new_dict[pattern.strip()] = replacement.strip()
    return new_dict

def preprocess_cs_text(text: str) -> str:
    t = text.lower()
    for pattern, replacement in CS_SLANG.items():
        t = re.sub(pattern, replacement, t)
    return t

def clean_string(text: str) -> str:
    return re.sub(r'[\u200e\u200f\u202a-\u202e\x01\x02\x03\x04\x05\x06\x07\x08\r\n]', '', text).strip()

def sanitize_text(text: str) -> str:
    return text.replace('"', '').replace(';', '').strip()

def send_via_cfg(is_team: bool, text: str):
    cmd = "say_team" if is_team else "say"
    safe_text = sanitize_text(text)

    if not safe_text:
        return

    with open(CFG_PATH, "w", encoding="utf-8") as f:
        f.write(f'{cmd} "{safe_text}"\n')

    time.sleep(0.2)
    keyboard.send(TRIGGER_KEY)

def process_and_translate(message: str, is_team: bool):
    global is_active
    if not is_active:
        return

    try:
        is_caps = message.isupper()

        prepped = preprocess_cs_text(message)
        if re.search(r'[а-яА-ЯёЁ]', prepped):
            translated = argostranslate.translate.translate(prepped, "ru", "en")
        else:
            translated = prepped

        if is_caps:
            translated = translated.upper()

        send_via_cfg(is_team, translated.strip())
    except Exception:
        pass

def handle_command(command_str: str, is_team: bool):
    global is_active
    cmd = command_str.strip().lower()

    if cmd == "!translate off":
        is_active = False
        send_via_cfg(is_team, "[Translator] OFF")
        return True
    elif cmd == "!translate on":
        is_active = True
        send_via_cfg(is_team, "[Translator] ON")
        return True
    elif cmd == "!tstatus":
        status_text = "ENABLED" if is_active else "DISABLED"
        send_via_cfg(is_team, f"[Translator] Status: {status_text}")
        return True
    
    return False

def main():
    global CS_SLANG, is_active, MY_NICKNAME
    
    MY_NICKNAME = get_steam_nickname()
    my_nick_clean = clean_string(MY_NICKNAME).lower()
    CS_SLANG = load_dictionary()

    if not os.path.exists(LOG_PATH):
        return

    print("Running...")

    last_sent_time = 0
    last_message = ""

    with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        last_size = os.path.getsize(LOG_PATH)

        while True:
            current_size = os.path.getsize(LOG_PATH)
            
            if current_size < last_size:
                f.seek(0, os.SEEK_SET)
                last_size = current_size

            line = f.readline()
            if not line:
                time.sleep(0.05)
                continue

            line_clean = clean_string(line)
            if ": " not in line_clean:
                continue

            left_part, message = line_clean.split(": ", 1)
            message = message.strip()

            left_lower = left_part.lower()
            if my_nick_clean in left_lower:
                is_team_chat = "[всем]" not in left_lower

                if message.startswith("!"):
                    if handle_command(message, is_team_chat):
                        continue
                
                if is_active and re.search(r'[а-яА-ЯёЁ]', message):
                    current_time = time.time()
                    
                    if current_time - last_sent_time > 0.3 or message != last_message:
                        process_and_translate(message, is_team_chat)
                        last_sent_time = current_time
                        last_message = message

            last_size = current_size



if __name__ == "__main__":
    main()
