import asyncio
import re
import os
import sys
import time
import uuid
import json
import httpx
import aiofiles
from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote, urlparse, parse_qs

# CDM 环境检测
try:
    from pywidevine.cdm import Cdm
    from pywidevine.device import Device
    from pywidevine.pssh import PSSH
    HAS_CDM = True
except ImportError:
    HAS_CDM = False

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TransferSpeedColumn, TaskID
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import print as rprint
from playwright.async_api import async_playwright, Response, Request, Page, Route

# 全局常量
CONFIG_FILE = "wanwan_config.json"
CACHE_PREFIX = "wanwan_cache_"
console = Console()


# -------------------------------------------------------------------------
# ⚙️ 皇室配置管家 (Config Manager)
# -------------------------------------------------------------------------


class ConfigManager:
    # 默认配置表 (皇上的御用标准)
    DEFAULTS = {
        "download_dir": "Royal_OnlyFans_Collection",
        "wvd_path": "./device.wvd",
        "re_tool_path": "N_m3u8DL-RE",
        "chrome_path": "",
        "proxy": "",
        "concurrency": 50,
        "timeout": 30
    }

    # 配置项说明文案
    DESCRIPTIONS = {
        "download_dir": "📂 战利品存放目录",
        "wvd_path": "🔑 CDM 设备文件路径 (device.wvd)",
        "re_tool_path": "🛠️ N_m3u8DL-RE 工具路径 (可填绝对路径)",
        "chrome_path": "🌐 Google Chrome 路径 (留空则自动识别)",
        "proxy": "🌍 HTTP 代理地址 (如 http://127.0.0.1:7890)",
        "concurrency": "⚡ 并发下载数量 (建议 10-50)",
        "timeout": "⏳ 网络请求超时时间 (秒)"
    }

    def __init__(self):
        self.config = self.DEFAULTS.copy()
        self.load()

    def load(self):
        """从文件加载配置，如果没有则使用默认"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.config.update(saved)
            except Exception as e:
                rprint(f"[red]配置文件加载失败: {e}，将使用默认值[/red]")

    def save(self):
        """保存配置到文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            rprint("[green]✅ 配置已保存到小账本！[/green]")
        except Exception as e:
            rprint(f"[red]保存失败: {e}[/red]")

    def get(self, key: str) -> Any:
        return self.config.get(key, self.DEFAULTS.get(key))

    def setup_wizard(self):
        """交互式配置向导"""
        console.clear()
        rprint(
            Panel.fit("[bold magenta]⚙️ 皇室配置中心[/bold magenta]", border_style="magenta"))

        while True:
            # 显示当前配置表
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("序号", style="dim", width=4)
            table.add_column("配置项", style="bold")
            table.add_column("当前值", style="yellow")
            table.add_column("说明", style="white")

            keys = list(self.DEFAULTS.keys())
            for idx, key in enumerate(keys):
                val = self.config.get(key)
                if key == "chrome_path" and not val:
                    val = "[自动识别]"
                if key == "proxy" and not val:
                    val = "[直连]"
                table.add_row(str(idx + 1), key, str(val),
                              self.DESCRIPTIONS[key])

            console.print(table)
            rprint("\n[dim]输入序号修改配置，输入 'q' 保存并退出[/dim]")

            choice = Prompt.ask("您的选择", default="q")

            if choice.lower() == 'q':
                self.save()
                break

            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(keys):
                    key = keys[idx]
                    desc = self.DESCRIPTIONS[key]
                    current = self.config.get(key)

                    rprint(f"\n[bold cyan]正在修改: {key}[/bold cyan]")
                    rprint(f"说明: {desc}")

                    if isinstance(self.DEFAULTS[key], int):
                        new_val = IntPrompt.ask(
                            f"请输入新数值 (当前: {current})", default=current)
                    else:
                        new_val = Prompt.ask(f"请输入新值 (当前: {current})", default=str(
                            current) if current else "")
                        # 特殊处理空值
                        if key == "proxy" and (new_val.lower() == "none" or new_val == ""):
                            new_val = ""

                    self.config[key] = new_val
                    rprint("[green]已更新！[/green]\n")
                else:
                    rprint("[red]无效的序号[/red]")


# 初始化全局配置
cfg = ConfigManager()


# -------------------------------------------------------------------------
# 📦 数据模型
# -------------------------------------------------------------------------


class Asset:
    def __init__(self, media_id, post_id, text, url, media_type, posted_at, filename=None, source_type="post", is_drm=False, drm_info=None, key=None):
        self.media_id = str(media_id)  # 👑 新增：这是唯一的！
        self.post_id = str(post_id)
        self.text = text
        self.url = url
        self.media_type = media_type
        self.posted_at = posted_at
        self.source_type = source_type
        self.is_drm = is_drm
        self.drm_info = drm_info or {}
        self.key = key
        self.filename = filename if filename else self._generate_filename()

    def _generate_filename(self) -> str:
        # 1. 清洗文案
        clean_text = re.sub(r'<[^>]+>', '', self.text if self.text else "")
        clean_text = re.sub(r'[\\/:*?"<>|\n\r]', '', clean_text).strip()[:80]
        if not clean_text:
            clean_text = f"untitled_{uuid.uuid4().hex[:8]}"

        # 2. 👑 动态后缀获取：不再硬编码！
        # 从 URL 的 path 部分直接切下后缀 (例如 .webp, .avi, .m4a)
        parsed_url = urlparse(self.url)
        ext = os.path.splitext(parsed_url.path)[1].lower()

        # 3. 🛡️ 异常兜底：如果 URL 里没后缀，按类型打补丁
        if not ext:
            if self.is_drm or self.media_type == "video":
                ext = ".mp4"
            elif self.media_type == "photo":
                ext = ".jpg"
            elif self.media_type == "audio":
                ext = ".mp3"

        prefix = ""
        if self.source_type == "archived":
            prefix += "[Archived]"
        if self.is_drm:
            prefix += "[DRM]"
        if prefix:
            prefix += "_"

        # 👑 皇上御赐修正：加入 media_id 防止重名覆盖！
        # 格式：[前缀]postID_mediaID-文案.后缀
        return f"{prefix}{self.post_id}_{self.media_id}-{clean_text}{ext}"

    def to_dict(self):
        return {
            "media_id": self.media_id, "post_id": self.post_id, "text": self.text, "url": self.url,
            "media_type": self.media_type, "posted_at": self.posted_at,
            "filename": self.filename, "source_type": self.source_type,
            "is_drm": self.is_drm, "drm_info": self.drm_info, "key": self.key
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            media_id=data.get("media_id", "0"),  # 兼容旧缓存
            post_id=data["post_id"], text=data["text"], url=data["url"],
            media_type=data["media_type"], posted_at=data["posted_at"],
            filename=data.get("filename"), source_type=data.get("source_type", "post"),
            is_drm=data.get("is_drm", False), drm_info=data.get("drm_info", {}),
            key=data.get("key")
        )


# -------------------------------------------------------------------------
# 🕵️‍♀️ 核心逻辑
# -------------------------------------------------------------------------


class WanWanScraper:
    def __init__(self, user_id: str, download_mode: str):
        self.user_id = user_id
        self.download_mode = download_mode
        self.assets: Dict[str, Asset] = {}

        # 从配置读取路径
        base_dir_name = cfg.get("download_dir")
        self.base_dir = (Path(os.getcwd()) / base_dir_name / user_id).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.has_more = True

        # 从配置读取代理
        self.proxy = cfg.get("proxy")
        # 👑 [新增] 初始化用户名变量
        self.username = None

    def archive_manifest(self):
        """🗂️ 归档：在下载文件夹里生成一份精美的战利品清单"""
        try:
            # 准备清单文件路径
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            manifest_name = f"manifest_{timestamp}.json"
            manifest_path = self.base_dir / manifest_name

            # 汇总所有捕获到的资源数据
            # 我们直接把 assets 字典里的对象都转成 dict 存进去
            data = {
                "user_id": self.user_id,
                "archive_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_count": len(self.assets),
                "download_mode": self.download_mode,
                "assets": [asset.to_dict() for asset in self.assets.values()]
            }

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            rprint(f"[bold cyan]📜 战利品清单已归档至下载目录: {manifest_name}[/bold cyan]")
        except Exception as e:
            rprint(f"[red]❌ 清单归档失败: {e}[/red]")

    async def process_api_response(self, response: Response):
        """解析 API"""
        try:
            # 同时也监听 audios 相关的 API
            if ("/users/" in response.url and "/posts" in response.url) and response.status == 200:
                source_type = "archived" if "archived" in response.url else "post"
                data = await response.json()
                if "hasMore" in data:
                    self.has_more = data["hasMore"]
                if "list" in data:
                    for post in data["list"]:
                        if "media" not in post:
                            continue
                        post_id = post.get("id")
                        text = post.get("text", "")
                        posted_at = post.get("postedAtPrecise")

                        for media in post["media"]:
                            m_type = media.get("type")
                            media_id = media.get("id")  # 👑 获取 media_id

                            # 模式过滤
                            if self.download_mode == "photos" and m_type != "photo":
                                continue
                            if self.download_mode == "videos" and m_type != "video":
                                continue
                            if self.download_mode == "audios" and m_type != "audio":
                                continue

                            source = None
                            is_drm = False
                            drm_info = {}

                            files = media.get("files", {})
                            source = files.get("full", {}).get("url")

                            # DRM 处理
                            if not source and "drm" in files:
                                drm = files["drm"]
                                manifest = drm.get("manifest", {})
                                hls_url = manifest.get(
                                    "dash") or manifest.get("hls")
                                if hls_url:
                                    sig_key = "dash" if "mpd" in hls_url else "hls"
                                    sig = drm.get("signature", {}).get(
                                        sig_key, {})
                                    if sig.get("CloudFront-Policy"):
                                        policy = sig["CloudFront-Policy"]
                                        signature = sig["CloudFront-Signature"]
                                        kpid = sig["CloudFront-Key-Pair-Id"]
                                        source = f"{hls_url}?Policy={policy}&Signature={
                                            signature}&Key-Pair-Id={kpid}"
                                        is_drm = True
                                        drm_info = {
                                            "media_id": media_id,
                                            "post_id": post_id,
                                        }

                            # 保底
                            if not source and m_type in ["video", "audio"]:
                                v_src = media.get("videoSources", {})
                                source = v_src.get("720") or v_src.get(
                                    "240") or v_src.get("source")

                            if source and source not in self.assets:
                                # 👑 传入 media_id
                                asset = Asset(media_id, post_id, text, source, m_type, posted_at,
                                              source_type=source_type, is_drm=is_drm, drm_info=drm_info)
                                self.assets[source] = asset
        except Exception:
            pass

    async def _scroll_page(self, page, description="抓取中"):
        self.has_more = True
        no_change_count = 0
        last_height = await page.evaluate("document.body.scrollHeight")
        with console.status(f"[bold magenta]正在{description}...[/bold magenta]") as status:
            while True:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.0)  # 稍微快一点
                new_height = await page.evaluate("document.body.scrollHeight")
                status.update(f"[bold magenta]🚀 {description}... 已捕获: {
                              len(self.assets)}[/bold magenta]")
                if new_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 5:
                        if not self.has_more:
                            break
                        else:
                            await page.evaluate("window.scrollBy(0, -500)")
                            await asyncio.sleep(0.5)
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    if no_change_count >= 8:
                        break
                else:
                    no_change_count = 0
                    last_height = new_height

    # -------------------------------------------------------------------------
    # 👑 第一阶段：普通下载
    # -------------------------------------------------------------------------
    async def download_normal_assets(self):
        normal_assets = [a for a in self.assets.values() if not a.is_drm]
        if not normal_assets:
            return

        rprint(Panel(f"[bold cyan]第一阶段：下载 {
               len(normal_assets)}/{len(self.assets)} 个普通资源[/bold cyan]", border_style="cyan"))

        concurrency = cfg.get("concurrency")
        timeout = cfg.get("timeout")

        semaphore = asyncio.Semaphore(concurrency)
        limits = httpx.Limits(
            max_keepalive_connections=concurrency, max_connections=concurrency)
        client_kwargs = {"timeout": timeout,
                         "limits": limits, "follow_redirects": True}

        if self.proxy:
            client_kwargs["proxy"] = self.proxy
        else:
            client_kwargs["trust_env"] = True

        async with httpx.AsyncClient(**client_kwargs) as client:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("{task.percentage:>3.0f}%"), TransferSpeedColumn(), console=console) as progress:
                main_task = progress.add_task(
                    "[cyan]普通资源下载[/cyan]", total=len(normal_assets))
                tasks = [self.download_worker(
                    client, asset, progress, main_task, semaphore, is_drm_tool=False) for asset in normal_assets]
                await asyncio.gather(*tasks)

    # -------------------------------------------------------------------------
    # 👑 第二阶段：DRM 猎杀 (拦截重放模式)
    # -------------------------------------------------------------------------
    async def hunt_drm_keys(self, page: Page):
        drm_assets = [a for a in self.assets.values()
                      if a.is_drm and not a.key]
        if not drm_assets:
            return

        wvd_path = cfg.get("wvd_path")
        if not HAS_CDM or not os.path.exists(wvd_path):
            rprint(f"[red]❌ 缺少 CDM 或未找到 {wvd_path}，无法进行猎杀！[/red]")
            return

        rprint(Panel(
            f"[bold red]第二阶段：DRM 猎杀模式 - 目标 {len(drm_assets)} 个[/bold red]", border_style="red"))

        # 加载 CDM
        device = Device.load(wvd_path)
        cdm = Cdm.from_device(device)
        session_id = cdm.open()

        # --- 👑 全局状态控制 ---
        # 我们用这个字典在“拦截器”和“主循环”之间传递数据
        # current_challenge: 当前视频计算出的 Challenge (二进制)
        # captured_license: 拦截器抓到的 License (二进制)
        state = {
            "current_challenge": None,
            "captured_license": None,
            "is_hunting": True
        }

        # --- 👑 定义全局拦截器 (增强版拦截器：自带 3 次重试) ---
        async def global_interceptor(route: Route, request: Request):
            if "/drm/" in request.url and request.method == "POST":
                rprint(f"[dim]🎣 嗅探到 DRM 请求[/dim]")

                if state["current_challenge"]:
                    # 尝试 3 次发送
                    for attempt in range(3):
                        try:
                            # 发起请求 (timeout 设长一点，防止代理慢)
                            response = await route.fetch(post_data=state["current_challenge"], timeout=15000)

                            if response.status == 200:
                                body = await response.body()
                                state["captured_license"] = body
                                rprint("[green]⚡️ License 捕获成功！[/green]")
                            else:
                                # 如果是 4xx/5xx 错误，那是服务器拒绝，重试也没用，直接打印
                                rprint(f"[red]❌ License服务器拒绝: {
                                       response.status}[/red]")

                            # 无论成功失败，只要网络通了，就完成请求
                            await route.fulfill(response=response)
                            return

                        except Exception as e:
                            # 👑 这里捕获 Socket disconnected 错误
                            if attempt < 2:
                                # rprint(f"[dim]⚠️ 网络抖动 ({e})，正在重试拦截...[/dim]")
                                await asyncio.sleep(1)  # 歇一秒让代理缓口气
                            else:
                                rprint(f"[red]❌ Hook 彻底失败 (网络问题): {e}[/red]")
                                await route.continue_()  # 放弃抵抗，放行原请求
                                return

            # 其他请求一律放行
            await route.continue_()

        # 开启全局拦截网
        await page.route("**/*", global_interceptor)

        # 确保回到顶部，开始扫荡
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)

        # 备用 httpx 用于下载 MPD (获取 PSSH 用)
        httpx_kwargs = {"timeout": 10, "verify": False}
        if self.proxy:
            httpx_kwargs["proxy"] = self.proxy

        async with httpx.AsyncClient(**httpx_kwargs) as mpd_client:

            for i, asset in enumerate(drm_assets):
                # 👑 建议：每处理 50 个视频，休息 2 秒，防止代理过热
                if i > 0 and i % 50 == 0:
                    rprint("[dim]☕ 休息一下，让代理服务器喘口气...[/dim]")
                    await asyncio.sleep(2)

                # 👑 最外层鲁棒性循环：每个视频最多尝试 5 次
                for attempt in range(5):
                    try:
                        if attempt > 0:
                            rprint(f"[yellow]⚠️ 第 {
                                   attempt+1} 次重试: {asset.post_id}...[/yellow]")
                        else:
                            rprint(
                                f"[yellow]⚔️ ({i+1}/{len(drm_assets)}) 正在猎杀: {asset.filename[:20]}...[/yellow]")

                        # 1. 预备阶段：获取 PSSH 并计算 Challenge
                        # (这步必须在点击播放前完成，否则拦截器没子弹)
                        pssh_b64 = None
                        try:
                            # 优先用 Playwright 自身的上下文下载 MPD (带 Cookie)
                            resp = await page.request.get(asset.url, timeout=5000)
                            if resp.status == 200:
                                xml_text = await resp.text()
                            else:
                                raise Exception("Playwright fetch failed")
                        except:
                            # Fallback 到 httpx
                            headers = {"User-Agent": "Mozilla/5.0"}
                            if "cf_cookie" in asset.drm_info:
                                headers["Cookie"] = asset.drm_info["cf_cookie"]
                            resp = await mpd_client.get(asset.url, headers=headers)
                            xml_text = resp.text
                            pssh_b64 = None

                        # 精准定位 PSSH
                        widevine_uuid = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
                        uuid_index = xml_text.find(widevine_uuid)
                        if uuid_index != -1:
                            start_tag = "<cenc:pssh>"
                            end_tag = "</cenc:pssh>"
                            pssh_start_idx = xml_text.find(
                                start_tag, uuid_index)
                            if pssh_start_idx != -1:
                                pssh_end_idx = xml_text.find(
                                    end_tag, pssh_start_idx)
                                if pssh_end_idx != -1:
                                    pssh_b64 = xml_text[pssh_start_idx +
                                                        len(start_tag):pssh_end_idx].strip()

                        rprint(f"[dim]🔑 PSSH: {pssh_b64}[/dim]")

                        if not pssh_b64:
                            rprint("[red]❌ PSSH 获取失败，跳过[/red]")
                            continue  # 重试

                        # 计算 Challenge 并装填给拦截器
                        # 注意：每次都要重新生成 session_id 对应的 challenge
                        # 为了简单，我们复用一个 session，或者每次 close/open。这里复用 session。
                        challenge_bytes = cdm.get_license_challenge(
                            session_id, PSSH(pssh_b64))

                        # ♻️ 重置状态
                        state["current_challenge"] = challenge_bytes
                        state["captured_license"] = None

                        # 2. 搜索阶段：👑 皇上御赐极简点击逻辑
                        # 直接去帖子页
                        if self.username:
                            target_url = f"https://onlyfans.com/{
                                asset.post_id}/{self.username}"
                        else:
                            target_url = f"https://onlyfans.com/{
                                asset.post_id}"

                        rprint(f"[cyan]🚀 直达: {target_url}[/cyan]")
                        await page.goto(target_url, wait_until="domcontentloaded")

                        # 👑 皇上御赐：10秒智能等待逻辑
                        clicked = False
                        wait_start_time = time.time()

                        # 循环检测按钮是否出现 (最多等10秒)
                        while time.time() - wait_start_time < 10:
                            # 优先找大按钮
                            if await page.locator(".vjs-big-play-button").is_visible():
                                await page.locator(".vjs-big-play-button").first.click()
                                clicked = True
                                break

                            # 备选找视频标签 (有些皮肤没有大按钮)
                            if await page.locator("video").is_visible():
                                # 确保不是头图，而是真正的视频元素
                                await page.locator("video").first.click()
                                clicked = True
                                break

                            await asyncio.sleep(0.5)  # 每0.5秒看一眼

                        if not clicked:
                            rprint(
                                "[dim]⚠️ 10秒内未找到播放按钮，可能已自动播放或加载慢，尝试强制等待...[/dim]")

                        # 3. 捕获阶段：等待 License
                        # 点击后，页面会弹出模态框并自动播放，拦截器会在后台工作
                        wait_start = time.time()
                        got_it = False
                        while time.time() - wait_start < 30:  # 最多等TIMEOUT秒
                            if state["captured_license"]:
                                got_it = True
                                break
                            await asyncio.sleep(0.2)

                        if got_it:
                            # 4. 解密阶段
                            try:
                                cdm.parse_license(
                                    session_id, state["captured_license"])
                                keys = cdm.get_keys(session_id)
                                for key in keys:
                                    if key.type == "CONTENT":
                                        asset.key = f"{key.kid.hex}:{
                                            key.key.hex()}"
                                        rprint(f"[bold green]🔑 解密成功: {
                                            asset.key}[/bold green]")
                                        break

                                self.save_cache()
                                break  # 成功，跳出重试循环
                            except Exception as e:
                                rprint(f"[red]❌ License 解析失败: {e}[/red]")
                        else:
                            rprint("[red]⚠️ 捕获超时 (视频未自动播放？)[/red]")
                            # 没有捕获到，抛出异常以触发重试
                            raise Exception("Capture Timeout")
                    except Exception as e:
                        rprint(f"[red]💥 尝试失败: {e}[/red]")
                        # 复位页面状态，为下一次重试做准备
                        try:
                            await page.keyboard.press("Escape")
                            await asyncio.sleep(1)
                        except:
                            pass
                        # 继续下一次重试循环
                        continue

        # 结束清理
        cdm.close(session_id)
        await page.unroute("**/*")
        self.save_cache()

    # -------------------------------------------------------------------------
    # 👑 第三阶段：DRM 下载 (调用 N_m3u8DL-RE)
    # -------------------------------------------------------------------------
    async def download_drm_assets(self):
        # 只有拿到了 Key 的 DRM 视频才下载
        unlocked_assets = [
            a for a in self.assets.values() if a.is_drm and a.key]
        if not unlocked_assets:
            return

        rprint(Panel(f"[bold green]第三阶段：下载 {
               len(unlocked_assets)} 个已解密视频[/bold green]", border_style="green"))

        semaphore = asyncio.Semaphore(5)  # DRM 下载比较耗CPU，并发低一点
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("{task.percentage:>3.0f}%"), console=console) as progress:
            main_task = progress.add_task(
                "[green]解密下载中[/green]", total=len(unlocked_assets))
            # 对于 RE 工具，不需要 httpx client，直接调用子进程
            tasks = [self.download_worker(
                None, asset, progress, main_task, semaphore, is_drm_tool=True) for asset in unlocked_assets]
            await asyncio.gather(*tasks)

    async def download_worker(self, client, asset: Asset, progress, main_task_id: TaskID, semaphore, is_drm_tool=False):
        # 👑 使用 .part 临时文件，防止损坏文件污染目录
        final_path = self.base_dir / asset.filename
        temp_path = self.base_dir / f"{asset.filename}.part"

        # 重新读取配置，因为可能在运行时修改
        re_path = cfg.get("re_tool_path")

        async with semaphore:
            # 1. 检查已存在的完整文件
            if final_path.exists() and final_path.stat().st_size > 0:
                # 这里可以加一个简单的逻辑：如果本地文件太小（比如0字节），视为损坏，重新下
                if final_path.stat().st_size > 1024:
                    progress.advance(main_task_id)
                    return
                else:
                    os.remove(final_path)  # 删除垃圾文件

            # 📺 DRM 下载 (RE工具自带校验，我们只负责调用)
            if is_drm_tool and asset.key:
                try:
                    progress.update(
                        main_task_id, description=f"[red]RE[/red] {asset.filename[:20]}")
                    parsed = urlparse(asset.url)
                    clean_url = f"{
                        parsed.scheme}://{parsed.netloc}{parsed.path}"
                    params = parse_qs(parsed.query)
                    policy = params.get('Policy', [''])[0]
                    signature = params.get('Signature', [''])[0]
                    kpid = params.get('Key-Pair-Id', [''])[0]
                    cookie_str = f"CloudFront-Policy={policy}; CloudFront-Signature={
                        signature}; CloudFront-Key-Pair-Id={kpid}"

                    cmd = [
                        re_path,
                        clean_url,
                        "--save-dir", str(self.base_dir),
                        "--save-name", asset.filename.replace(".mp4", ""),
                        "--header", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "--header", f"Cookie: {cookie_str}",
                        "--key", asset.key,
                        "--auto-select", "--no-log", "-mt", "--mux-after-done", "mp4"
                    ]
                    if self.proxy:
                        cmd.extend(["--custom-proxy", self.proxy])

                    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                    await proc.wait()

                    # RE 工具如果生成了文件，一般是完整的，简单校验一下存在性
                    if final_path.exists():
                        pass
                    elif proc.returncode != 0:
                        rprint(f"[red]RE失败: {asset.filename}[/red]")
                except Exception as e:
                    rprint(f"[red]RE异常: {e}[/red]")

            # 📸 普通下载 (图片/视频/音频) - 👑 重点修复区域！
            elif not is_drm_tool and client:
                # 重试机制：最多试3次
                for attempt in range(3):
                    try:
                        progress.update(main_task_id, description=f"[blue]DL({
                                        attempt+1})[/blue] {asset.filename[:15]}")

                        headers = {"User-Agent": "Mozilla/5.0"}

                        # 发起请求
                        async with client.stream("GET", asset.url, headers=headers, follow_redirects=True) as response:
                            if response.status_code != 200:
                                rprint(f"[red]HTTP {
                                       response.status_code}[/red]")
                                if response.status_code == 404:
                                    break  # 404就不重试了
                                continue  # 其他错误重试

                            # 👑 获取预期大小
                            total_size = int(
                                response.headers.get('Content-Length', 0))

                            # 下载到 .part
                            downloaded_size = 0
                            async with aiofiles.open(temp_path, "wb") as f:
                                async for chunk in response.aiter_bytes():
                                    if chunk:
                                        await f.write(chunk)
                                        downloaded_size += len(chunk)

                            # 👑 完整性校验！
                            # 如果服务器给了长度，且下载长度不一致，说明断流了！
                            if total_size > 0 and downloaded_size != total_size:
                                raise Exception(f"Incomplete download: {
                                                downloaded_size}/{total_size}")

                            # 校验通过，改名转正
                            if os.path.exists(temp_path):
                                os.rename(temp_path, final_path)

                            # 成功，跳出重试循环
                            break

                    except Exception as e:
                        rprint(f"[dim]下载中断: {e}，重试中...[/dim]")
                        await asyncio.sleep(1)  # 歇一秒再试
                        if os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)  # 删掉坏的
                            except:
                                pass

                    # 如果3次都失败，最后清理一下
                    if attempt == 2 and not final_path.exists():
                        rprint(f"[red]❌ 彻底失败: {asset.filename}[/red]")

            progress.advance(main_task_id)

    # -------------------------------------------------------------------------
    # 👑 主控流程
    # -------------------------------------------------------------------------
    async def start_scraping(self, no_scroll=False):
        # 👑 使用持久化目录 (免登录)
        user_data_dir = os.path.join(os.getcwd(), "browser_data")
        # 👑 从配置读取 Chrome 路径
        executable_path = cfg.get("chrome_path")

        if executable_path == "":
            # 1. 👑 自动识别操作系统并设置 Chrome 路径
            if sys.platform == "darwin":  # macOS
                executable_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            else:  # Windows
                executable_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

            if not os.path.exists(executable_path):
                rprint(f"[bold red]❌ 未找到 Chrome: {executable_path}[/bold red]")
                return

        rprint(f"[cyan]🔧 Chrome 路径: {executable_path}[/cyan]")
        rprint(f"[cyan]📂 数据目录: {user_data_dir}[/cyan]")

        # 2. 👑 关键：定义要“屏蔽”的默认参数
        # Playwright 默认会加一堆禁用后台服务的参数，我们要把它们“黑名单”掉，
        # 这样 Chrome 才会去下载 Widevine 组件。
        ignore_default_args = [
            "--enable-automation",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-component-extensions-with-background-pages",
            "--disable-component-update",  # <--- 罪魁祸首！必须忽略这个 flag
            "--disable-background-networking",  # <--- 这个也会阻止组件下载
            "--disable-sync",
        ]

        # 3. 👑 定义我们要“添加”的参数
        args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",  # 隐藏 WebDriver 特征
            "--enable-encrypted-media",  # 显式开启 DRM
            "--allow-running-insecure-content",
        ]
        # 👑 构造 Proxy 配置
        proxy_config = None
        if self.proxy:
            proxy_config = {"server": self.proxy}
            rprint(f"[cyan]🌐 使用代理: {self.proxy}[/cyan]")

        async with async_playwright() as p:
            rprint("[yellow]🚀 正在启动浏览器... (第一次可能需要几十秒下载组件)[/yellow]")

            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    executable_path=executable_path,
                    channel="chrome",
                    headless=False,
                    args=args,
                    ignore_default_args=ignore_default_args,  # 👈 应用我们的黑名单
                    viewport=None,
                    proxy=proxy_config,  # 👈 必须加上这个！
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            except Exception as e:
                rprint(f"[bold red]启动失败: {e}[/bold red]")
                return

            page = context.pages[0]

            # 4. 注入隐身脚本 (保持不变)
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    navigator.permissions.query(parameters)
                );
            """)

            # 5. 👑 组件自愈检查逻辑
            # 如果组件是空的，我们需要暂停，让人工介入去触发下载
            rprint("[cyan]🔍 检查 Widevine 组件状态...[/cyan]")

            # 打开组件页面
            await page.goto("chrome://components", wait_until="commit")

            await page.wait_for_timeout(2500)  # 等待页面加载

            # 这里的逻辑是：如果检测到页面上没有 Widevine，提示用户
            is_widevine_present = await page.evaluate("""
                () => document.body.innerText.includes("Widevine Content Decryption Module")
            """)

            if not is_widevine_present:
                rprint(Panel.fit(
                    "[bold red]⚠️ 警告：Widevine 组件尚未安装！[/bold red]\n\n"
                    "请在弹出的浏览器中手动操作：\n"
                    "1. 页面应该已经是 [bold]chrome://components[/bold]\n"
                    "2. 找到 [bold]Widevine Content Decryption Module[/bold]\n"
                    "3. 点击 [bold]Check for update[/bold]\n"
                    "4. 如果列表是空的，请等待 1-2 分钟，Chrome 正在后台静默下载...\n"
                    "5. 下载完成后刷新页面确认版本号不为 0.0.0.0\n\n"
                    "[green]确认组件出现后，按回车继续...[/green]",
                    title="👑 需要人工辅助"
                ))
                input("按回车继续...")
            else:
                rprint("[green]✅ 检测到 Widevine 组件！[/green]")

            # 6. 再次检测 DRM API (双重保险)
            try:
                is_ok = await page.evaluate("""
                    async () => {
                        try {
                            const config = [{ initDataTypes: ['cenc'], videoCapabilities: [{ contentType: 'video/mp4; codecs="avc1.42E01E"' }] }];
                            await navigator.requestMediaKeySystemAccess('com.widevine.alpha', config);
                            return true;
                        } catch (e) { return false; }
                    }
                """)
                if not is_ok:
                    rprint(
                        "[bold red]❌ DRM API 调用依然失败！请尝试删除 browser_data 目录重试。[/bold red]")
                    await context.close()
                    return
            except:
                pass

            # 4. 登录/跳转
            page.on("response", self.process_api_response)
            login_url = f"https://onlyfans.com/?return_to={
                quote(f'/{self.user_id}/media')}"

            rprint(f"[cyan]🌐 前往: {login_url}[/cyan]")
            await page.goto(login_url, wait_until="domcontentloaded")

            # 等待加载
            try:
                await page.wait_for_url(f"**/{self.user_id}/media", timeout=0)
                await page.wait_for_selector(".user_posts", state="visible", timeout=0)
                # 👑 [新增] 截获用户名逻辑
                # 此时 URL 应该是 https://onlyfans.com/{username}/media
                # 万能正则：匹配两个斜杠中间的任意字符(非 / 的所有字符)
                # 这样不管是中文、Emoji、还是 URL 编码，统统都能抓到！
                match = re.search(r'onlyfans\.com/([^/]+)/media', page.url)
                if match:
                    self.username = match.group(1)
                    rprint(f"[green]✅ 捕获用户名: {self.username}[/green]")
                else:
                    rprint("[yellow]⚠️ 未能提取用户名，将使用 ID 进行尝试...[/yellow]")
            except:
                rprint("[yellow]⚠️ 跳转超时，可能需要手动登录或验证...[/yellow]")

            # 5. 抓取 API
            if not no_scroll:
                await self._scroll_page(page, "扫荡主页")
                self.save_cache()

            # -----------------------------------------------------------------
            # 🚀 执行三步走战略
            # -----------------------------------------------------------------

            # Step 1: 先下容易的 (此时浏览器开着没事，让它待机)
            await self.download_normal_assets()

            # Step 2: 浏览器出动，猎杀 DRM (Hook + Replay)
            await self.hunt_drm_keys(page)

            # Step 3: 下载 DRM 视频 (此时浏览器任务完成，可以关了，也可以留着)
            await context.close()
            await self.download_drm_assets()

            # 就是这里！大功告成后把清单写进去
            self.archive_manifest()

            rprint(Panel("[bold green]🎉 全流程任务结束！[/bold green]",
                   border_style="green"))

    def save_cache(self):
        try:
            with open(f"{CACHE_PREFIX}{self.user_id}.json", "w", encoding="utf-8") as f:
                json.dump({url: asset.to_dict() for url, asset in self.assets.items(
                )}, f, indent=4, ensure_ascii=False)
        except:
            pass

    def load_cache(self) -> bool:
        cache_file = f"{CACHE_PREFIX}{self.user_id}.json"
        if os.path.exists(cache_file):
            if Confirm.ask(f"[bold green]发现本地缓存 ({cache_file})，是否使用？[/bold green]"):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for url, item in data.items():
                        asset = Asset.from_dict(item)
                        if self.download_mode == "photos" and asset.media_type != "photo":
                            continue
                        if self.download_mode == "videos" and asset.media_type != "video":
                            continue
                        self.assets[url] = asset
                    return True
                except:
                    pass
        return False


# -------------------------------------------------------------------------
# 🚀 CLI 入口
# -------------------------------------------------------------------------


def get_valid_user_id() -> str:
    while True:
        uid = Prompt.ask("[cyan]请输入博主的 ID (纯数字)[/cyan]", default="76031078")
        if uid.strip().isdigit():
            return uid.strip()
        rprint("[bold red]❌ ID 必须全是数字！[/bold red]")


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    rprint(Panel.fit(
        "[bold magenta]💖 OnlyFans 皇室专属下载器 (终极配置管理版) 💖[/bold magenta]", border_style="magenta"))
    rprint("[dim]皇上，按 's' 进入详细配置，按其他键直接开始[/dim]")

    # 简单的启动菜单
    start_choice = Prompt.ask("指令", default="go")

    if start_choice.lower() == 's':
        cfg.setup_wizard()
        # 配置完后重新加载界面
        os.system('cls' if os.name == 'nt' else 'clear')
        rprint(Panel.fit(
            "[bold magenta]💖 配置已更新，准备起飞 💖[/bold magenta]", border_style="magenta"))

    user_id = get_valid_user_id()

    rprint("\n[yellow]模式选择：[/yellow]\n1. 📸 仅图片\n2. 🎥 仅视频\n3. 🎵 仅音频\n4. 📦 我全都要")
    choice = Prompt.ask("请选择", choices=["1", "2", "3", "4"], default="4")
    mode_map = {"1": "photos", "2": "videos", "3": "audios", "4": "all"}

    # 从配置中读取代理
    scraper = WanWanScraper(user_id, mode_map[choice])

    try:
        if scraper.load_cache():
            if Confirm.ask("直接开始下载/解密？(选No则重新抓取API)", default=True):
                asyncio.run(scraper.start_scraping(True))
            else:
                asyncio.run(scraper.start_scraping(False))
        else:
            asyncio.run(scraper.start_scraping())
    except KeyboardInterrupt:
        rprint("\n[bold red]🛑 任务已暂停。[/bold red]")
    except Exception as e:
        rprint(f"\n[bold red]💥 发生意外: {e}[/bold red]")


if __name__ == "__main__":
    main()
