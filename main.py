"""
AudioControl — 侧边栏：配置家电与「操作 → 语音文案」；使用页通过 Edge TTS 播报。
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import flet as ft
import flet_audio as fta

import tts_edge

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def new_appliance(name: str = "新家电") -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "name": name,
        "commands": [],
    }


def new_command(operation: str = "新操作", phrase: str = "") -> dict:
    return {"operation": operation, "phrase": phrase}


def load_config() -> list[dict]:
    if not CONFIG_PATH.is_file():
        return []
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        items = raw.get("appliances", [])
        return items if isinstance(items, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_config(appliances: list[dict]) -> None:
    CONFIG_PATH.write_text(
        json.dumps({"appliances": appliances}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def show_message(page: ft.Page, text: str) -> None:
    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(text),
            duration=ft.Duration(milliseconds=1000),
        )
    )


def main(page: ft.Page) -> None:
    page.title = "AudioControl"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 960
    page.window.height = 640
    page.window.min_width = 720
    page.window.min_height = 480

    appliances: list[dict] = load_config()
    if not appliances:
        appliances.append(new_appliance("示例：客厅灯"))
        appliances[0]["commands"].extend(
            [
                new_command("关灯", "关灯"),
                new_command("开灯", "开灯"),
            ]
        )

    right = ft.Container(expand=True, padding=24)
    bottom_nav = ft.NavigationBar(
        selected_index=0,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="配置"),
            ft.NavigationBarDestination(icon=ft.Icons.MIC, label="使用"),
        ],
    )

    def on_nav_change(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if idx == 0:
            refresh_config_panel()
        else:
            refresh_use_panel()

    bottom_nav.on_change = on_nav_change

    page.navigation_bar = bottom_nav

    use_dropdown = ft.Ref[ft.Dropdown]()
    use_commands_column = ft.Ref[ft.Column]()

    # 音频播放器
    audio = fta.Audio(
            autoplay=False,
            volume=1,
            balance=0,
            release_mode=fta.ReleaseMode.RELEASE,)
    page.services.append(audio)

    def persist() -> None:
        save_config(appliances)
        show_message(page, "已保存，正在后台更新语音缓存…")

        def cache_worker() -> None:
            try:
                gen, skip = tts_edge.warm_cache(appliances)
                removed = tts_edge.prune_stale_cache(appliances)
                print(f"[语音缓存] 新建 {gen}，已有 {skip}，清理旧文件 {removed}")

                async def done() -> None:
                    show_message(page, "配置与语音缓存已更新。")

                page.run_task(done)
            except Exception as ex:

                async def err(e: BaseException = ex) -> None:
                    show_message(page, f"语音缓存失败：{e}")

                page.run_task(err)

        page.run_thread(cache_worker)

    def build_command_rows(appliance: dict) -> list[ft.Control]:
        rows: list[ft.Control] = []

        def remove_cmd(cmd: dict) -> None:
            if cmd in appliance["commands"]:
                appliance["commands"].remove(cmd)
                refresh_config_panel()

        for cmd in appliance["commands"]:
            op = ft.TextField(
                label="操作",
                value=cmd["operation"],
                expand=True,
                dense=True,
                on_change=lambda e, c=cmd: c.__setitem__("operation", e.control.value),
            )
            ph = ft.TextField(
                label="语音内容（后续接 TTS）",
                value=cmd["phrase"],
                expand=True,
                dense=True,
                on_change=lambda e, c=cmd: c.__setitem__("phrase", e.control.value),
            )
            rows.append(
                ft.Row(
                    [
                        op,
                        ph,
                        ft.IconButton(
                            icon=ft.Icons.DELETE,
                            on_click=lambda _, c=cmd: remove_cmd(c),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        def add_cmd(_: ft.ControlEvent | None = None) -> None:
            appliance["commands"].append(new_command())
            refresh_config_panel()

        rows.append(ft.OutlinedButton("添加一条指令", icon=ft.Icons.ADD, on_click=add_cmd))
        return rows

    def build_appliance_card(appliance: dict) -> ft.Control:
        def remove_appliance(_: ft.ControlEvent) -> None:
            appliances.remove(appliance)
            refresh_config_panel()
            refresh_use_panel()

        name_field = ft.TextField(
            label="家电名称",
            value=appliance["name"],
            on_change=lambda e, a=appliance: a.__setitem__("name", e.control.value),
        )

        return ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("家电", size=16, weight=ft.FontWeight.W_600),
                                ft.Container(expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE,
                                    tooltip="删除家电",
                                    on_click=remove_appliance,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        name_field,
                        ft.Text("操作与语音", size=14, weight=ft.FontWeight.W_500),
                        *build_command_rows(appliance),
                    ],
                    spacing=12,
                    tight=True,
                ),
            )
        )

    def refresh_config_panel() -> None:
        cards = [build_appliance_card(a) for a in appliances]

        def add_appliance(_: ft.ControlEvent | None = None) -> None:
            appliances.append(new_appliance())
            refresh_config_panel()
            refresh_use_panel()

        right.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("配置", size=22, weight=ft.FontWeight.W_600),
                        ft.Container(expand=True),
                        ft.FilledButton("保存", icon=ft.Icons.SAVE, on_click=lambda _: persist()),
                        ft.OutlinedButton("添加家电", icon=ft.Icons.ADD, on_click=add_appliance),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Text(
                    "每个家电下可添加多条：操作名称 + 语音文案。点击「保存」会写入配置并生成/更新语音缓存（audio_cache）。",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=8),
                ft.ListView(controls=cards, expand=True, spacing=12, padding=0),
            ],
            expand=True,
            spacing=0,
        )
        page.update()

    def on_command_click(phrase: str) -> None:
        if not (phrase or "").strip():
            show_message(page, "语音文案为空，请在配置页填写。")
            return

        # show_message(page, "正在准备语音…")

        async def run_tts_flow() -> None:
            try:
                print(f"[Edge TTS] 开始准备：{phrase!r}")
                path, hit = await asyncio.to_thread(tts_edge.ensure_and_get_path, phrase)
                # print(f"[Edge TTS] 缓存文件：{path}；命中={hit}")
                show_message(page, f"缓存文件：{path}；命中={hit}")
            except Exception as ex:
                # show_message(page, "生成语音失败")
                show_message(page, f"TTS 失败：{ex}")
                return

            try:
                 # 1. 在 Android 上直接传入字符串绝对路径是最稳的
                # audio.src = "https://github.com/mdn/webaudio-examples/blob/main/audio-analyser/viper.mp3?raw=true"
                #@if page.platform == ft.PagePlatform.WINDOWS:
                os.startfile(str(path))
                path = path.resolve().as_uri()
                audio.src = path
                # await asyncio.sleep(0.5)
                print(f"[Edge TTS] 音频源：{audio.src}")
                await audio.play() 

            except Exception as play_ex:
                show_message(page, f"播放失败：{play_ex}")
                print(f"[Edge TTS] flet-audio 播放失败：{play_ex!r}")
                return
            print(f"[Edge TTS] 已播放(flet-audio) {'(缓存)' if hit else '(新生成)'}：{phrase!r}")

        page.run_task(run_tts_flow)

    def refresh_use_panel() -> None:
        opts = [ft.dropdown.Option(key=a["id"], text=a["name"]) for a in appliances]

        def rebuild_buttons(appliance_id: str | None) -> None:
            col = use_commands_column.current
            if col is None:
                return
            col.controls.clear()
            if not appliance_id:
                col.controls.append(ft.Text("请先添加家电。", color=ft.Colors.ON_SURFACE_VARIANT))
                page.update()
                return
            app = next((a for a in appliances if a["id"] == appliance_id), None)
            if not app:
                col.controls.append(ft.Text("未找到该家电。", color=ft.Colors.ON_SURFACE_VARIANT))
                page.update()
                return
            cmds = app.get("commands") or []
            if not cmds:
                col.controls.append(ft.Text("该家电暂无指令，请在配置页添加。", color=ft.Colors.ON_SURFACE_VARIANT))
            else:
                for c in cmds:
                    op = c.get("operation", "")
                    phrase = c.get("phrase", "")
                    col.controls.append(
                        ft.FilledButton(
                            op or "（未命名操作）",
                            on_click=lambda _, p=phrase: on_command_click(p),
                        )
                    )
            page.update()

        def on_dd_select(e: ft.ControlEvent) -> None:
            rebuild_buttons(e.control.value)

        dd = ft.Dropdown(
            ref=use_dropdown,
            label="选择家电",
            options=opts,
            width=320,
            on_select=on_dd_select,
        )
        if opts:
            # 保持当前选中若仍存在，否则选第一项
            current = dd.value
            ids = [o.key for o in opts]  # type: ignore[attr-defined]
            if current not in ids:
                dd.value = opts[0].key  # type: ignore[attr-defined]
        else:
            dd.value = None

        right.content = ft.Column(
            [
                ft.Text("使用", size=22, weight=ft.FontWeight.W_600),
                ft.Text(
                    "选择家电后点击操作：优先播放已缓存的语音；保存配置时会预下载缺失的缓存（需联网）。",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=16),
                dd,
                ft.Container(height=16),
                ft.Text("操作", size=14, weight=ft.FontWeight.W_500),
                ft.Column(ref=use_commands_column, spacing=10, tight=True),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
        page.update()
        rebuild_buttons(dd.value)



    page.add(right)
    refresh_config_panel()


if __name__ == "__main__":
    ft.run(main)
