import flet as ft
import pytz
import os
import requests
import json
import pproxy
import asyncio
import geoip2.database
from functools import lru_cache
import time
from timezonefinder import TimezoneFinder
from playwright.async_api import async_playwright
from playwright.async_api._generated import BrowserContext

COUNTRY_DATABASE_PATH = "GeoLite2-Country.mmdb"
CITY_DATABASE_PATH = "GeoLite2-City.mmdb"
HARDWARE_DATA_PATH = "hardware.json"
LAPTOP_MODELS_PATH = os.path.join("hardware", "laptop_models.json")
DEVICE_DATA_PATH = os.path.join("hardware", "devices.json")
PROXY_DATA_PATH = "proxies.json"

SCREENS = ("800×600", "960×540", "1024×768", "1152×864", "1280×720", "1280×768", "1280×800", "1280×1024", "1366×768", "1408×792", "1440×900", "1400×1050", "1440×1080", "1536×864", "1600×900", "1600×1024", "1600×1200", "1680×1050", "1920×1080", "1920×1200", "2048×1152", "2560×1080", "2560×1440", "3440×1440")
LANGUAGES = ("en-US", "en-GB", "fr-FR", "ru-RU", "es-ES", "pl-PL", "pt-PT", "nl-NL", "zh-CN")
TIMEZONES = pytz.common_timezones
USER_AGENT = requests.get("https://raw.githubusercontent.com/microlinkhq/top-user-agents/refs/heads/master/src/index.json").json()[0]


def load_hardware_data() -> dict:
    """Load hardware specification data from JSON file.

    If the file doesn't exist, create it with a minimal ASUS laptop
    configuration and return that default data.
    """
    if os.path.isfile(HARDWARE_DATA_PATH):
        with open(HARDWARE_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    default_data = {
        "ASUS": {
            "laptop": {
                "mainboards": {
                    "ROG STRIX B550": {
                        "cpu": ["Ryzen 5 5600X", "Ryzen 7 5800X"],
                        "ram": ["8GB", "16GB", "32GB"],
                        "gpu": ["RTX 3060", "RTX 3070"],
                        "sound": ["Realtek ALC1220"]
                    },
                    "TUF Gaming B560M": {
                        "cpu": ["Intel i5-11400", "Intel i7-11700"],
                        "ram": ["8GB", "16GB"],
                        "gpu": ["GTX 1660", "RTX 2060"],
                        "sound": ["Realtek ALC897"]
                    }
                }
            }
        }
    }

    with open(HARDWARE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(default_data, f, indent=4)

    return default_data


def load_laptop_models_data() -> dict:
    """Load laptop models data from JSON file and create defaults if missing."""
    if os.path.isfile(LAPTOP_MODELS_PATH):
        with open(LAPTOP_MODELS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    default_data = {
        "ASUS": {
            "models": {
                "Zephyrus G14": {
                    "mainboards": ["ROG STRIX B550"],
                    "mouse": ["Touchpad"],
                    "battery": ["76Wh"]
                }
            }
        }
    }

    os.makedirs(os.path.dirname(LAPTOP_MODELS_PATH), exist_ok=True)
    with open(LAPTOP_MODELS_PATH, "w", encoding="utf-8") as f:
        json.dump(default_data, f, indent=4)

    return default_data


def load_device_data() -> dict:
    """Load device/OS/manufacturer mapping, creating defaults if missing."""
    if os.path.isfile(DEVICE_DATA_PATH):
        with open(DEVICE_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    default_data = {
        "Windows": {
            "laptop": ["ASUS", "APPLE"],
            "pc": ["ASUS"]
        }
    }

    os.makedirs(os.path.dirname(DEVICE_DATA_PATH), exist_ok=True)
    with open(DEVICE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(default_data, f, indent=4)

    return default_data


def load_proxies_data() -> list:
    """Load proxy list from JSON file, creating empty list if missing."""
    if os.path.isfile(PROXY_DATA_PATH):
        with open(PROXY_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    with open(PROXY_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump([], f, indent=4)

    return []


def save_proxies_data(data: list) -> None:
    """Save proxy list to JSON file."""
    with open(PROXY_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


async def check_proxy(proxy: str) -> dict:
    """Return proxy status and latency using TCP connection."""
    protocol = proxy.split("://")[0]
    if "@" in proxy:
        addr = proxy.split("@")[1]
    else:
        addr = proxy.split("://")[1]
    ip, port = addr.split(":")[:2]
    start = time.monotonic()
    try:
        reader, writer = await asyncio.open_connection(ip, int(port))
        writer.close()
        await writer.wait_closed()
        latency = int((time.monotonic() - start) * 1000)
        alive = True
    except Exception:
        latency = None
        alive = False

    info = get_proxy_info(ip)
    info.update({"latency": latency, "alive": alive, "protocol": protocol})
    return info


async def check_all_proxies(data: list) -> list:
    """Check all proxies and update their info."""
    for entry in data:
        result = await check_proxy(entry["proxy"])
        entry.update(result)
    return data

async def save_cookies(context: BrowserContext, profile: str) -> None:
    cookies = await context.cookies()

    for cookie in cookies:
        cookie.pop("sameSite", None)

    with open(f"cookies/{profile}", "w", encoding="utf-8") as f:
        json.dump(obj=cookies, fp=f, indent=4)

def parse_netscape_cookies(netscape_cookie_str: str) -> list[dict]:
    print(netscape_cookie_str)
    cookies = []
    lines = netscape_cookie_str.strip().split("\n")

    for line in lines:
        if not line.startswith("#") and line.strip():
            parts = line.split()
            if len(parts) == 7:
                cookie = {
                    "domain": parts[0],
                    "httpOnly": parts[1].upper() == "TRUE",
                    "path": parts[2],
                    "secure": parts[3].upper() == "TRUE",
                    "expires": float(parts[4]),
                    "name": parts[5],
                    "value": parts[6]
                }
                cookies.append(cookie)
    
    return cookies

@lru_cache(maxsize=256)
def get_proxy_info(ip: str) -> dict:
    with geoip2.database.Reader(COUNTRY_DATABASE_PATH) as reader:
        try:
            response = reader.country(ip)
            country_code = response.country.iso_code
        except geoip2.errors.AddressNotFoundError:
            country_code = "UNK"

    with geoip2.database.Reader(CITY_DATABASE_PATH) as reader:
        try:
            response = reader.city(ip)
            city = response.city.name if response.city.name else "UNK"
            timezone = TimezoneFinder().timezone_at(lng=response.location.longitude, lat=response.location.latitude)
        except geoip2.errors.AddressNotFoundError:
            city = "UNK"

    return {"country_code": country_code, "city": city, "timezone": timezone}

async def run_proxy(protocol: str, ip: str, port: int, login: str, password: str):
    server = pproxy.Server("socks5://127.0.0.1:1337")
    remote = pproxy.Connection(f"{protocol}://{ip}:{port}#{login}:{password}")
    args = dict(rserver = [remote],
                verbose = print)
    
    await server.start_server(args)

async def run_browser(user_agent: str, height: int, width: int, timezone: str, lang: str, proxy: str | bool, cookies: dict | bool, webgl: bool, vendor: str, cpu: int, ram: int, is_touch: bool, profile: str) -> None:
    async with async_playwright() as p:
        args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--ignore-certificate-errors",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-blink-features=AutomationControlled",
            ]
        
        if webgl is False:
            args.append("--disable-webgl")
        
        if proxy:
            protocol = proxy.split("://")[0]

            if "@" in proxy:
                splitted = proxy.split("://")[1].split("@")

                ip = splitted[1].split(":")[0]
                port = int(splitted[1].split(":")[1])
                username = splitted[0].split(":")[0]
                password = splitted[0].split(":")[1]
            else:
                splitted = proxy.split("://")[1].split(":")

                ip = splitted[0]
                port = int(splitted[1])
                username = splitted[2]
                password = splitted[3]

            if protocol == "http":
                proxy_settings = {
                    "server": f"{ip}:{port}",
                    "username": username,
                    "password": password
                }
            else:
                proxy_task = asyncio.create_task(run_proxy(protocol, ip, port, username, password))

                proxy_settings = {
                    "server": "socks5://127.0.0.1:1337"
                }

            browser = await p.chromium.launch(headless=False, proxy=proxy_settings, args=args)
        else:
            browser = await p.chromium.launch(headless=False, args=args)

        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": width, "height": height},
            locale=lang,
            timezone_id=timezone,
            has_touch=is_touch
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'vendor', {
                    get: function() {
                        return '""" + vendor + """';
                    }
                });
        """)

        await context.add_init_script("""
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: function() {
                        return """ + str(cpu) + """;
                    }
                });
        """)

        await context.add_init_script("""
            Object.defineProperty(navigator, 'deviceMemory', {
                    get: function() {
                        return """ + str(ram) + """;
                    }
                });
        """)

        if not os.path.isfile(f"cookies/{profile}") and cookies:
            with open(cookies, "r", encoding="utf-8") as f:
                cookies = f.read()
                try:
                    cookies_parsed = json.loads(cookies)
                except json.decoder.JSONDecodeError:
                    cookies_parsed = parse_netscape_cookies(cookies)
        elif os.path.exists(f"cookies/{profile}"):
            with open(f"cookies/{profile}", "r", encoding="utf-8") as f:
                try:
                    cookies_parsed = json.loads(f.read())
                except json.decoder.JSONDecodeError:
                    cookies_parsed = ()
        else:
            cookies_parsed = ()

        for cookie in cookies_parsed:
            cookie["sameSite"] = "Strict"
            await context.add_cookies([cookie])
        
        page = await context.new_page()

        await page.evaluate("navigator.__proto__.webdriver = undefined;")
        
        await page.goto("about:blank")

        try:
            await page.wait_for_event("close", timeout=0)
        finally:
            if not protocol == "http":
                proxy_task.cancel()
            await save_cookies(context, profile)

def main(page: ft.Page):
    page.title = "Antic Browser"
    page.adaptive = True

    def config_load(profile: str):
        with open(f"config/{profile}", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        asyncio.run(run_browser(config["user-agent"], config["screen_height"], config["screen_width"], config["timezone"], config["lang"], config["proxy"], config["cookies"], config["webgl"], config["vendor"], config["cpu"], config["ram"], config["is_touch"], profile))

    def delete_profile(profile: str):
        os.remove(f"config/{profile}")

        page.controls = get_config_content()
        page.update()

    def get_config_content():
        configs = []

        for cfg in os.listdir("config"):
            with open(f"config/{cfg}", "r", encoding="utf-8") as f:
                config = json.load(f)

            configs.append(ft.Container(bgcolor=ft.Colors.WHITE24, padding=20, border_radius=20, content=ft.Row([
                ft.Row([
                    ft.Text(cfg.rsplit(".", 1)[0], size=20, weight=ft.FontWeight.W_600),
                    ft.FilledButton(text=config["lang"], icon="language", bgcolor=ft.Colors.WHITE24, color=ft.Colors.WHITE, icon_color=ft.Colors.WHITE, style=ft.ButtonStyle(padding=20)),
                    ft.FilledButton(text=config["timezone"], icon="schedule", bgcolor=ft.Colors.WHITE24, color=ft.Colors.WHITE, icon_color=ft.Colors.WHITE, style=ft.ButtonStyle(padding=20))
                ]),
                ft.Row([
                    ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.WHITE70, on_click=lambda _: delete_profile(cfg)),
                    ft.FilledButton(text="Bắt đầu", icon="play_arrow", style=ft.ButtonStyle(padding=20), on_click=lambda _: config_load(cfg))
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))

        if len(configs) > 0:
            config_content = [ft.Column(
            controls=[
                ft.Text("Cấu hình", size=20),
                ft.Column(
                    controls=configs
                )
            ],
            spacing=20,
            expand=True,
            scroll=ft.ScrollMode.ALWAYS,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )]
        else:
            config_content = [ft.Row(
                [
                    ft.Text("Cấu hình", size=20)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )]

        return config_content

    def get_proxy():
        return load_proxies_data()

    def remove_proxy(proxy_url: str):
        data = load_proxies_data()
        data = [p for p in data if p.get("proxy") != proxy_url]
        save_proxies_data(data)
        page.controls = get_proxies_content()
        page.update()

    def add_proxy(e):
        data = load_proxies_data()
        proxy_url = add_proxy_field.value
        if proxy_url:
            data.append({"proxy": proxy_url})
            save_proxies_data(data)
            add_proxy_field.value = ""
            page.controls = get_proxies_content()
            page.update()

    def check_all(e):
        data = load_proxies_data()
        data = asyncio.run(check_all_proxies(data))
        save_proxies_data(data)
        page.controls = get_proxies_content()
        page.update()

    def get_proxies_content():
        proxies = []
        global add_proxy_field

        add_proxy_field = ft.TextField(hint_text="proxy", expand=True, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)

        for entry in get_proxy():
            proxy_str = entry["proxy"]
            ip = proxy_str.split("@")[1] if "@" in proxy_str else proxy_str.split("://")[1]
            ip = ip.split(":")[0]
            info = get_proxy_info(ip)
            latency = entry.get("latency")
            alive = entry.get("alive")

            status_color = ft.Colors.GREEN if alive else ft.Colors.RED

            proxies.append(ft.Container(bgcolor=ft.Colors.WHITE24, padding=20, border_radius=20, content=ft.Row([
                ft.Text(proxy_str, size=20, weight=ft.FontWeight.W_600),
                ft.FilledButton(text=info["country_code"], icon="flag", bgcolor=ft.Colors.WHITE24, color=ft.Colors.WHITE, icon_color=ft.Colors.WHITE, style=ft.ButtonStyle(padding=20)),
                ft.FilledButton(text=str(latency) if latency else "-", icon="speed", bgcolor=ft.Colors.WHITE24, color=status_color, icon_color=status_color, style=ft.ButtonStyle(padding=20)),
                ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.WHITE70, on_click=lambda _, p=proxy_str: remove_proxy(p))
            ])))

        if len(proxies) > 0:
            list_content = ft.Column(controls=proxies)
        else:
            list_content = ft.Text("Proxy", size=20)

        proxies_content = [ft.Column(
            controls=[
                ft.Row([
                    ft.Text("Proxy", size=20),
                    ft.IconButton(icon=ft.Icons.CHECK, on_click=check_all),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    add_proxy_field,
                    ft.IconButton(icon=ft.Icons.ADD, on_click=add_proxy)
                ], alignment=ft.MainAxisAlignment.START),
                list_content
            ],
            spacing=20,
            expand=True,
            scroll=ft.ScrollMode.ALWAYS,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )]

        return proxies_content

    def save_config(e):
        profile_name = profile_name_field.value
        user_agent_value = user_agent_field.value if user_agent_field.value else USER_AGENT
        screen_value = screen_dropdown.value if screen_dropdown.value else "1920×1080"
        timezone_value = timezone_dropdown.value if timezone_dropdown.value else "Europe/Moscow"
        language_value = language_dropdown.value if language_dropdown.value else "ru-RU"
        proxy_value = proxy_dropdown.value if proxy_dropdown.value else False
        if proxy_value:
            addr = proxy_value.split("@")[1] if "@" in proxy_value else proxy_value.split("://")[1]
            ip = addr.split(":")[0]
            timezone_value = get_proxy_info(ip).get("timezone", timezone_value)
        cookies_value = cookies_field.value if cookies_field.value else False
        webgl_value = webgl_switch.value
        vendor_value = vendor_field.value if vendor_field.value else "Google Inc."
        cpu_threads_value = int(cpu_threads_field.value) if int(cpu_threads_field.value) else 6
        ram_value = int(ram_field.value) if int(ram_field.value) else 6
        is_touch_value = is_touch_switch.value
        os_value = os_dropdown.value if os_dropdown.value else ""
        device_type_value = device_type_dropdown.value if device_type_dropdown.value else ""
        manufacturer_value = manufacturer_dropdown.value if manufacturer_dropdown.value else ""
        model_value = model_dropdown.value if model_dropdown.value else ""
        mainboard_value = mainboard_dropdown.value if mainboard_dropdown.value else ""
        hw_cpu_value = cpu_dropdown.value if cpu_dropdown.value else ""
        hw_ram_value = ram_dropdown.value if ram_dropdown.value else ""
        hw_gpu_value = gpu_dropdown.value if gpu_dropdown.value else ""
        hw_sound_value = sound_dropdown.value if sound_dropdown.value else ""
        mouse_value = mouse_dropdown.value if mouse_dropdown.value else ""
        battery_value = battery_dropdown.value if battery_dropdown.value else ""

        with open(f"config/{profile_name}.json", "w", encoding="utf-8") as f:
            json.dump(obj={
                "user-agent": user_agent_value,
                "screen_height": int(screen_value.split("×")[1]),
                "screen_width": int(screen_value.split("×")[0]),
                "timezone": timezone_value,
                "lang": language_value,
                "proxy": proxy_value,
                "cookies": cookies_value,
                "webgl": webgl_value,
                "vendor": vendor_value,
                "cpu": cpu_threads_value,
                "ram": ram_value,
                "is_touch": is_touch_value,
                "os": os_value,
                "device_type": device_type_value,
                "manufacturer": manufacturer_value,
                "model": model_value,
                "mainboard": mainboard_value,
                "hw_cpu": hw_cpu_value,
                "hw_ram": hw_ram_value,
                "hw_gpu": hw_gpu_value,
                "hw_sound": hw_sound_value,
                "mouse": mouse_value,
                "battery": battery_value
            }, fp=f, indent=4)

        page.controls = get_config_content()
        page.update()

    def open_config_page(e):
        global profile_name_field, user_agent_field, screen_dropdown, timezone_dropdown, language_dropdown, proxy_dropdown, cookies_field, webgl_switch, vendor_field, cpu_threads_field, ram_field, is_touch_switch, os_dropdown, device_type_dropdown, manufacturer_dropdown, model_dropdown, mainboard_dropdown, cpu_dropdown, ram_dropdown, gpu_dropdown, sound_dropdown, mouse_dropdown, battery_dropdown

        n = 1

        while True:
            if not os.path.isfile(f"config/Profile {n}.json"):
                break
            else:
                n += 1

        hardware = load_hardware_data()
        models_data = load_laptop_models_data()
        devices = load_device_data()
        asus_boards = hardware.get("ASUS", {}).get("laptop", {}).get("mainboards", {})

        def on_os_change(e):
            device_types = devices.get(os_dropdown.value, {})
            device_type_dropdown.options = [ft.dropdown.Option(dt) for dt in device_types.keys()]
            device_type_dropdown.value = None
            on_device_type_change(None)
            page.update()

        def on_device_type_change(e):
            manufacturers = []
            if os_dropdown.value:
                manufacturers = devices.get(os_dropdown.value, {}).get(device_type_dropdown.value, [])
            manufacturer_dropdown.options = [ft.dropdown.Option(m) for m in manufacturers]
            manufacturer_dropdown.value = None
            on_manufacturer_change(None)
            page.update()

        def on_manufacturer_change(e):
            models = models_data.get(manufacturer_dropdown.value, {}).get("models", {})
            model_dropdown.options = [ft.dropdown.Option(m) for m in models.keys()]
            model_dropdown.value = None
            on_model_change(None)
            page.update()

        def on_model_change(e):
            model_info = models_data.get(manufacturer_dropdown.value, {}).get("models", {}).get(model_dropdown.value, {})
            boards = model_info.get("mainboards", [])
            mainboard_dropdown.options = [ft.dropdown.Option(b) for b in boards]
            mainboard_dropdown.value = None
            mouse_dropdown.options = [ft.dropdown.Option(m) for m in model_info.get("mouse", [])]
            battery_dropdown.options = [ft.dropdown.Option(b) for b in model_info.get("battery", [])]
            mouse_dropdown.value = None
            battery_dropdown.value = None
            cpu_dropdown.options = []
            ram_dropdown.options = []
            gpu_dropdown.options = []
            sound_dropdown.options = []
            cpu_dropdown.value = None
            ram_dropdown.value = None
            gpu_dropdown.value = None
            sound_dropdown.value = None
            page.update()

        def on_mainboard_change(e):
            boards = hardware.get(manufacturer_dropdown.value, {}).get(device_type_dropdown.value or "laptop", {}).get("mainboards", {})
            specs = boards.get(mainboard_dropdown.value, {})
            cpu_dropdown.options = [ft.dropdown.Option(v) for v in specs.get("cpu", [])]
            ram_dropdown.options = [ft.dropdown.Option(v) for v in specs.get("ram", [])]
            gpu_dropdown.options = [ft.dropdown.Option(v) for v in specs.get("gpu", [])]
            sound_dropdown.options = [ft.dropdown.Option(v) for v in specs.get("sound", [])]
            cpu_dropdown.value = None
            ram_dropdown.value = None
            gpu_dropdown.value = None
            sound_dropdown.value = None
            page.update()

        profile_name_field = ft.TextField(label="Tên hồ sơ", value=f"Profile {n}", border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        user_agent_field = ft.TextField(hint_text="User Agent", value=USER_AGENT, expand=True, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        screen_dropdown = ft.Dropdown(
            label="Màn hình",
            value="1920×1080",
            width=300,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(screen) for screen in SCREENS]
        )
        timezone_dropdown = ft.Dropdown(
            label="Múi giờ",
            width=350,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(timezone) for timezone in TIMEZONES]
        )
        language_dropdown = ft.Dropdown(
            label="Ngôn ngữ",
            width=200,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(lang) for lang in LANGUAGES]
        )
        proxy_dropdown = ft.Dropdown(
            label="Proxy",
            expand=True,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(p["proxy"]) for p in get_proxy()]
        )
        cookies_field = ft.TextField(hint_text="Đường dẫn đến cookie", expand=True, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        webgl_switch = ft.Switch(
            adaptive=True,
            label="WebGL",
            value=False,
        )
        vendor_field = ft.TextField(label="Nhà sản xuất", value="Google Inc.", expand=True, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        cpu_threads_field = ft.TextField(label="Số luồng CPU", value=6, keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        ram_field = ft.TextField(label="RAM", value=6, keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        is_touch_switch = ft.Switch(
            adaptive=True,
            label="Cảm ứng",
            value=False,
        )

        os_dropdown = ft.Dropdown(
            label="OS",
            width=150,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(o) for o in devices.keys()],
            on_change=on_os_change,
        )
        device_type_dropdown = ft.Dropdown(
            label="Loại thiết bị",
            width=150,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            on_change=on_device_type_change,
        )

        manufacturer_dropdown = ft.Dropdown(
            label="Hãng",
            width=200,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            on_change=on_manufacturer_change,
        )
        model_dropdown = ft.Dropdown(
            label="Model",
            width=200,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            on_change=on_model_change,
        )

        mainboard_dropdown = ft.Dropdown(
            label="Mainboard",
            width=250,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[],
            on_change=on_mainboard_change,
        )
        cpu_dropdown = ft.Dropdown(label="CPU", width=200, border_color=ft.Colors.WHITE, border_radius=20)
        ram_dropdown = ft.Dropdown(label="RAM", width=150, border_color=ft.Colors.WHITE, border_radius=20)
        gpu_dropdown = ft.Dropdown(label="GPU", width=200, border_color=ft.Colors.WHITE, border_radius=20)
        sound_dropdown = ft.Dropdown(label="Sound", width=200, border_color=ft.Colors.WHITE, border_radius=20)
        mouse_dropdown = ft.Dropdown(label="Mouse", width=200, border_color=ft.Colors.WHITE, border_radius=20)
        battery_dropdown = ft.Dropdown(label="Battery", width=200, border_color=ft.Colors.WHITE, border_radius=20)

        page.controls = [ft.Column(
            controls=[
                ft.Text("Cấu hình mới", size=20),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            profile_name_field,
                            ft.FilledButton(text="Lưu", icon="check", style=ft.ButtonStyle(padding=20), on_click=save_config)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            user_agent_field,
                            screen_dropdown
                        ]
                    )
                ),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            timezone_dropdown,
                            language_dropdown,
                            proxy_dropdown
                        ]
                    ),
                ),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            cookies_field,
                            webgl_switch
                        ]
                    )
                ),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            vendor_field,
                            cpu_threads_field,
                            ram_field,
                            is_touch_switch
                        ]
                    )
                ),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            os_dropdown,
                            device_type_dropdown,
                            manufacturer_dropdown,
                            model_dropdown
                        ]
                    )
                ),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            mainboard_dropdown,
                            cpu_dropdown,
                            ram_dropdown,
                            gpu_dropdown,
                            sound_dropdown
                        ]
                    )
                ),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            mouse_dropdown,
                            battery_dropdown
                        ]
                    )
                )
            ],
            spacing=5,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )]

        page.update()

    def update_content(e):
        if e.control.selected_index == 0:
            page.appbar = ft.AppBar(
                title=ft.Text("Antic Browser"),
                actions=[
                    ft.IconButton(ft.CupertinoIcons.ADD, style=ft.ButtonStyle(padding=10), on_click=open_config_page)
                ],
                bgcolor=ft.Colors.with_opacity(0.04, ft.CupertinoColors.SYSTEM_BACKGROUND),
            )
            page.controls = get_config_content()
        elif e.control.selected_index == 1:
            page.appbar = ft.AppBar(
                title=ft.Text("Antic Browser"),
                actions=[],
                bgcolor=ft.Colors.with_opacity(0.04, ft.CupertinoColors.SYSTEM_BACKGROUND),
            )
            page.controls = get_proxies_content()

        page.update()

    page.appbar = ft.AppBar(
        title=ft.Text("Antic Browser"),
        actions=[
            ft.IconButton(ft.CupertinoIcons.ADD, style=ft.ButtonStyle(padding=10), on_click=open_config_page)
        ],
        bgcolor=ft.Colors.with_opacity(0.04, ft.CupertinoColors.SYSTEM_BACKGROUND),
    )

    page.navigation_bar = ft.NavigationBar(
        on_change=update_content,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.TUNE, label="Cấu hình"),
            ft.NavigationBarDestination(icon=ft.Icons.VPN_KEY, label="Proxy")
        ],
        border=ft.Border(
            top=ft.BorderSide(color=ft.CupertinoColors.SYSTEM_GREY2, width=0)
        ),
    )

    page.add(get_config_content()[0])

if __name__ == "__main__":
    if not os.path.isdir("config"):
        os.mkdir("config")

    if not os.path.isdir("cookies"):
        os.mkdir("cookies")

    if not os.path.isfile(COUNTRY_DATABASE_PATH):
        response = requests.get("https://git.io/GeoLite2-Country.mmdb")

        with open(COUNTRY_DATABASE_PATH, "wb") as file:
            file.write(response.content)

    if not os.path.isfile(CITY_DATABASE_PATH):
        response = requests.get("https://git.io/GeoLite2-City.mmdb")

        with open(CITY_DATABASE_PATH, "wb") as file:
            file.write(response.content)

    # ensure default hardware and laptop model data exist
    load_hardware_data()
    load_laptop_models_data()
    load_device_data()
    load_proxies_data()

    ft.app(main)
