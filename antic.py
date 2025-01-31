import flet as ft
import pytz
import os
import requests
import json
import asyncio
from playwright.async_api import async_playwright

screens = ("800×600", "960×540", "1024×768", "1152×864", "1280×720", "1280×768", "1280×800", "1280×1024", "1366×768", "1408×792", "1440×900", "1400×1050", "1440×1080", "1536×864", "1600×900", "1600×1024", "1600×1200", "1680×1050", "1920×1080", "1920×1200", "2048×1152", "2560×1080", "2560×1440", "3440×1440")
languages = ("en-US", "en-GB", "fr-FR", "ru-RU", "es-ES", "pl-PL", "pt-PT", "nl-NL", "zh-CN")
timezones = pytz.common_timezones
user_agent = requests.get("https://raw.githubusercontent.com/microlinkhq/top-user-agents/refs/heads/master/src/index.json").json()[0]

def main(page: ft.Page):
    page.title = "Antic Browser"
    page.adaptive = True

    async def run(user_agent: str, height: int, width: int, timezone: str, lang: str, proxy: str | bool, cookies: dict | bool, webgl: bool) -> None:
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
                if "@" in proxy:
                    splitted = proxy.split("@")

                    server = splitted[1]
                    username = splitted[0].split(":")[0]
                    password = splitted[0].split(":")[1]
                else:
                    splitted = proxy.split(":")

                    server = splitted[0] + ":" + splitted[1]
                    username = splitted[2]
                    password = splitted[3]

                proxy_settings = {
                    "server": server,
                    "username": username,
                    "password": password
                }

                browser = await p.chromium.launch(headless=False, proxy=proxy_settings, args=args)
            else:
                browser = await p.chromium.launch(headless=False, args=args)

            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": width, "height": height},
                locale=lang,
                timezone_id=timezone,
            )

            if cookies:
                with open(cookies, "r", encoding="utf-8") as f:
                    cookies_parsed = json.loads(f.read())

                for cookie in cookies_parsed:
                    cookie["sameSite"] = "Strict"
                    await context.add_cookies([cookie])
            
            page = await context.new_page()

            await page.evaluate("navigator.__proto__.webdriver = undefined;")
            
            await page.goto("https://iphey.com/leaks")

            while True:
                pass

    def run_browser(profile: str):
        with open(f"config/{profile}", "r", encoding="utf-8") as f:
            config = json.load(f)
            
        asyncio.run(run(config["user-agent"], config["screen_height"], config["screen_width"], config["timezone"], config["lang"], config["proxy"], config["cookies"], config["webgl"]))

    def delete_profile(profile: str):
        os.remove(f"config/{profile}")

        page.controls = get_config_content()
        page.update()

    def get_config_content():
        configs = []

        for cfg in os.listdir("config"):
            configs.append(ft.Container(bgcolor=ft.Colors.WHITE24, padding=20, border_radius=20, content=ft.Row([
                ft.Text(cfg.rsplit(".", 1)[0], size=20, weight=ft.FontWeight.W_600),
                ft.Row([
                    ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.WHITE70, on_click=lambda _: delete_profile(cfg)),
                    ft.FilledButton(text="Старт", icon="play_arrow", style=ft.ButtonStyle(padding=20), on_click=lambda _: run_browser(cfg))
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))

        if len(configs) > 0:
            config_content = [ft.Column(
            controls=[
                ft.Text("Конфиги", size=20),
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
                    ft.Text("Конфиги", size=20)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )]

        return config_content

    def get_proxy():
        proxies = []
        
        with open("proxies.txt", "r", encoding="utf-8") as f:
            for line in f.read().split("\n"):
                if len(line) > 0:
                    proxies.append(line)

        return proxies

    def get_proxies_content():
        proxies = []

        for line in get_proxy():
            proxies.append(ft.Container(bgcolor=ft.Colors.WHITE24, padding=20, border_radius=20, content=ft.Row([
                ft.Text(line, size=20, weight=ft.FontWeight.W_600)
            ])))

        if len(proxies) > 0:
            proxies_content = [ft.Column(
            controls=[
                ft.Text("Прокси (HTTP)", size=20),
                ft.Column(
                    controls=proxies
                )
            ],
            spacing=20,
            expand=True,
            scroll=ft.ScrollMode.ALWAYS,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER 
        )]
        else:
            proxies_content = [ft.Row(
                [
                    ft.Text("Прокси (HTTP)", size=20)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )]

        return proxies_content

    def save_config(e):
        profile_name = profile_name_field.value
        user_agent_value = user_agent_field.value if user_agent_field.value else user_agent
        screen_value = screen_dropdown.value if screen_dropdown.value else "1920×1080"
        timezone_value = timezone_dropdown.value if timezone_dropdown.value else "Europe/Helsinki"
        language_value = language_dropdown.value if language_dropdown.value else "en"
        proxy_value = proxy_dropdown.value if proxy_dropdown.value else False
        cookies_value = cookies_field.value if cookies_field.value else False
        webgl_value = webgl_switch.value

        with open(f"config/{profile_name}.json", "w", encoding="utf-8") as f:
            json.dump(obj={
                "user-agent": user_agent_value,
                "screen_height": int(screen_value.split("×")[1]),
                "screen_width": int(screen_value.split("×")[0]),
                "timezone": timezone_value,
                "lang": language_value,
                "proxy": proxy_value,
                "cookies": cookies_value,
                "webgl": webgl_value
            }, fp=f, indent=4)

        page.controls = get_config_content()
        page.update()

    def open_config_page(e):
        global profile_name_field, user_agent_field, screen_dropdown, timezone_dropdown, language_dropdown, proxy_dropdown, cookies_field, webgl_switch

        n = 1

        while True:
            if not os.path.isfile(f"config/Profile {n}.json"):
                break
            else:
                n += 1

        profile_name_field = ft.TextField(label="Имя профиля", value=f"Profile {n}", border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        user_agent_field = ft.TextField(hint_text="User Agent", value=user_agent, expand=True, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        screen_dropdown = ft.Dropdown(
            label="Экран",
            value="1920×1080",
            width=300,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(screen) for screen in screens]
        )
        timezone_dropdown = ft.Dropdown(
            label="Timezone",
            width=350,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(timezone) for timezone in timezones]
        )
        language_dropdown = ft.Dropdown(
            label="Язык",
            width=200,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(lang) for lang in languages]
        )
        proxy_dropdown = ft.Dropdown(
            label="Прокси",
            expand=True,
            border_color=ft.Colors.WHITE,
            border_radius=20,
            options=[ft.dropdown.Option(proxy) for proxy in get_proxy()]
        )
        cookies_field = ft.TextField(hint_text="Путь к куки (JSON)", expand=True, border_color=ft.Colors.WHITE, border_radius=20, content_padding=10)
        webgl_switch = ft.Switch(
            adaptive=True,
            label="WebGL",
            value=False,
        )

        page.controls = [ft.Column(
            controls=[
                ft.Text("Новый конфиг", size=20),
                ft.Container(
                    padding=20,
                    content=ft.Row(
                        [
                            profile_name_field,
                            ft.FilledButton(text="Сохранить", icon="check", style=ft.ButtonStyle(padding=20), on_click=save_config)
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
                        spacing=50,
                        controls=[
                            timezone_dropdown,
                            language_dropdown,
                            proxy_dropdown
                        ],
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
            ],
            spacing=5,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER 
        )]

        page.update()

    def update_content(e):
        if e.control.selected_index == 0:
            page.controls = get_config_content()
        elif e.control.selected_index == 1:
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
            ft.NavigationBarDestination(icon=ft.Icons.TUNE, label="Конфиги"),
            ft.NavigationBarDestination(icon=ft.Icons.VPN_KEY, label="Прокси")
        ],
        border=ft.Border(
            top=ft.BorderSide(color=ft.CupertinoColors.SYSTEM_GREY2, width=0)
        ),
    )

    page.add(get_config_content()[0])

ft.app(main)