import asyncio
import re
import os
import time
import uuid
import json
import httpx
import aiofiles
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    TaskID,
)
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint
from playwright.async_api import async_playwright, Response

# -------------------------------------------------------------------------
# 👑 皇上的配置区域
# -------------------------------------------------------------------------
DOWNLOAD_DIR = "Royal_OnlyFans_Collection"
CONFIG_FILE = "wanwan_config.json"
CACHE_PREFIX = "wanwan_cache_"
CONCURRENCY = 10
TIMEOUT = 30

console = Console()


class Asset:
    def __init__(self, post_id, text, url, media_type, posted_at, filename=None, source_type="post"):
        self.post_id = str(post_id)
        self.text = text
        self.url = url
        self.media_type = media_type
        self.posted_at = posted_at
        self.source_type = source_type  # 标记是主页(post)还是归档(archived)
        if filename:
            self.filename = filename
        else:
            self.filename = self._generate_filename()

    def _generate_filename(self) -> str:
        clean_text = re.sub(r'<[^>]+>', '', self.text if self.text else "")
        clean_text = re.sub(r'[\\/:*?"<>|\n\r]', '', clean_text).strip()
        if not clean_text:
            clean_text = f"untitled_{uuid.uuid4().hex[:8]}"

        # 👑 贴心标记：如果是挖坟挖出来的，文件名加个标记
        prefix = "[Archived]_" if self.source_type == "archived" else ""

        ext = ".jpg"
        if "mp4" in self.url or self.media_type == "video":
            ext = ".mp4"
        elif "jpg" in self.url or "jpeg" in self.url:
            ext = ".jpg"
        elif "png" in self.url:
            ext = ".png"
        return f"{prefix}{self.post_id}-{clean_text}{ext}"

    def to_dict(self):
        return {
            "post_id": self.post_id,
            "text": self.text,
            "url": self.url,
            "media_type": self.media_type,
            "posted_at": self.posted_at,
            "filename": self.filename,
            "source_type": self.source_type
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            post_id=data["post_id"],
            text=data["text"],
            url=data["url"],
            media_type=data["media_type"],
            posted_at=data["posted_at"],
            filename=data.get("filename"),
            source_type=data.get("source_type", "post")
        )


class WanWanScraper:
    def __init__(self, user_id: str, download_mode: str, auth_data: Optional[dict] = None, proxy: Optional[str] = None):
        self.user_id = user_id
        self.download_mode = download_mode
        self.auth_data = auth_data
        self.proxy = proxy
        self.assets: Dict[str, Asset] = {}
        self.base_dir = (Path(os.getcwd()) / DOWNLOAD_DIR / user_id).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.has_more = True

    async def process_api_response(self, response: Response):
        try:
            # 👑 核心升级：同时监听主页 Posts 和 归档 Archived
            # 主页: api2/v2/users/{id}/posts
            # 归档: api2/v2/users/{id}/posts/archived (或者类似的变体)
            # 所以我们放宽匹配规则，只要包含 users/{id}/posts 就算命中
            if f"/users/{self.user_id}/posts" in response.url and response.status == 200:
                # 区分一下来源，方便给文件名打标
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
                            source = None
                            if m_type == "photo":
                                source = media.get("files", {}).get(
                                    "full", {}).get("url")
                            elif m_type == "video":
                                files = media.get("files", {})
                                source = files.get("full", {}).get("url")
                                if not source:
                                    v_src = media.get("videoSources", {})
                                    source = v_src.get(
                                        "720") or v_src.get("240")

                            if source and source not in self.assets:
                                asset = Asset(
                                    post_id, text, source, m_type, posted_at, source_type=source_type)
                                self.assets[source] = asset
        except Exception:
            pass

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

    def archive_manifest(self):
        try:
            with open(self.base_dir / f"manifest_{time.strftime('%Y%m%d_%H%M%S')}.json", "w", encoding="utf-8") as f:
                json.dump([asset.to_dict() for asset in self.assets.values()],
                          f, indent=4, ensure_ascii=False)
        except:
            pass

    async def _scroll_page(self, page, description="抓取中"):
        """通用的滚动逻辑"""
        self.has_more = True  # 重置标记
        no_change_count = 0
        last_height = await page.evaluate("document.body.scrollHeight")

        with console.status(f"[bold magenta]琬琬正在{description}...[/bold magenta]") as status:
            while True:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)
                new_height = await page.evaluate("document.body.scrollHeight")

                status.update(f"[bold magenta]🚀 {description}... 已捕获: {
                              len(self.assets)}[/bold magenta]")

                if new_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 4:
                        if not self.has_more:
                            console.log(
                                f"[green]{description} - API 提示到底。[/green]")
                            break
                        else:
                            await page.evaluate("window.scrollBy(0, -300)")
                            await asyncio.sleep(0.5)
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    if no_change_count >= 6:
                        console.log(
                            f"[yellow]{description} - 高度不再变化，停止。[/yellow]")
                        break
                else:
                    no_change_count = 0
                    last_height = new_height

    async def start_scraping(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, args=["--mute-audio"])
            context = await browser.new_context()
            page = await context.new_page()
            page.on("response", self.process_api_response)

            # 登录部分
            target_path = f"/{self.user_id}/media"
            login_url = f"https://onlyfans.com/?return_to={quote(target_path)}"
            rprint(
                Panel.fit("[bold yellow]浏览器已启动！请登录...[/bold yellow]", title="👑 皇上请操作"))
            await page.goto(login_url)

            if self.auth_data:
                try:
                    rprint("[cyan]自动填充...[/cyan]")
                    try:
                        await page.wait_for_selector('input[name="email"]', timeout=3000)
                        if await page.is_visible('input[name="email"]'):
                            await page.fill('input[name="email"]', self.auth_data['email'])
                            await page.fill('input[type="password"]', self.auth_data['password'])
                            await page.click('button[type="submit"]')
                    except:
                        pass
                except:
                    pass

            rprint("[cyan]等待跳转...[/cyan]")
            try:
                await page.wait_for_url(f"https://onlyfans.com/**/media", timeout=0)
                await page.wait_for_selector(".user_posts", state="visible", timeout=TIMEOUT*1000)
                await asyncio.sleep(2)
            except Exception:
                await browser.close()
                return

            # --- 第一阶段：扫荡主页 (Media) ---
            rprint("[bold blue]========= 第一阶段：主页大扫荡 =========[/bold blue]")
            await self._scroll_page(page, "扫荡主页")

            # --- 第二阶段：挖坟 (Archived) ---
            rprint("\n[bold yellow]========= 第二阶段：深入冷宫挖坟 =========[/bold yellow]")
            archived_url = f"https://onlyfans.com/{self.user_id}/archived"
            rprint(f"[cyan]正在跳转至归档页: {archived_url}[/cyan]")

            await page.goto(archived_url)
            try:
                # 等待归档页加载，如果该用户没有归档页，可能会404或者跳转回主页
                # 我们简单判断一下，如果URL是对的，且有列表，就开始滚
                await asyncio.sleep(3)  # 等待跳转完成
                if "archived" in page.url:
                    # 尝试等待列表出现
                    try:
                        await page.wait_for_selector(".b-posts__list", state="visible", timeout=5000)
                        rprint("[green]发现归档内容！开始挖掘...[/green]")
                        await self._scroll_page(page, "挖掘归档")
                    except:
                        rprint("[dim]归档页似乎为空或加载失败。[/dim]")
                else:
                    rprint("[yellow]无法进入归档页（可能该博主没有归档内容）。[/yellow]")
            except Exception as e:
                rprint(f"[red]挖坟过程遇到小阻碍: {e}[/red]")

            await browser.close()
            self.save_cache()

            # 过滤下载
            if self.download_mode != "all":
                filtered = {}
                for url, asset in self.assets.items():
                    if self.download_mode == "photos" and asset.media_type == "photo":
                        filtered[url] = asset
                    elif self.download_mode == "videos" and asset.media_type == "video":
                        filtered[url] = asset
                self.assets = filtered

            await self.download_all()

    async def download_worker(self, client: httpx.AsyncClient, asset: Asset, progress: Progress, main_task_id: TaskID, semaphore: asyncio.Semaphore):
        file_path = self.base_dir / asset.filename
        async with semaphore:
            # 标记一下挖坟出来的文件
            desc = f"[gold1][挖坟][/gold1] " if asset.source_type == "archived" else "[blue][主页][/blue] "
            progress.update(main_task_id, description=f"{
                            desc}{asset.filename}...")

            if file_path.exists() and file_path.stat().st_size > 0:
                progress.advance(main_task_id)
                return

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            try:
                async with client.stream("GET", asset.url, headers=headers, follow_redirects=True) as response:
                    if response.status_code != 200:
                        progress.console.print(
                            f"[bold red]❌ 失败: {asset.filename}[/bold red]")
                        progress.advance(main_task_id)
                        return
                    async with aiofiles.open(file_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            await f.write(chunk)
            except Exception:
                pass
            finally:
                progress.advance(main_task_id)

    async def download_all(self):
        if not self.assets:
            rprint("[yellow]无资源。[/yellow]")
            return

        rprint(f"\n[bold green]📂 宝藏归档处:[/bold green] {self.base_dir}")
        rprint(f"[bold cyan]🚀 准备下载 {
               len(self.assets)} 个文件 (包含挖坟所得)...[/bold cyan]")

        semaphore = asyncio.Semaphore(CONCURRENCY)
        limits = httpx.Limits(
            max_keepalive_connections=CONCURRENCY, max_connections=CONCURRENCY)

        client_kwargs = {
            "timeout": TIMEOUT,
            "limits": limits,
            "follow_redirects": True
        }
        if self.proxy:
            client_kwargs["proxy"] = self.proxy
        else:
            client_kwargs["trust_env"] = True

        async with httpx.AsyncClient(**client_kwargs) as client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.percentage:>3.0f}%"),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                main_task = progress.add_task(
                    f"[bold yellow]总进度[/bold yellow]", total=len(self.assets))
                tasks = []
                for asset in self.assets.values():
                    tasks.append(self.download_worker(
                        client, asset, progress, main_task, semaphore))
                await asyncio.gather(*tasks)

        self.archive_manifest()
        rprint(
            Panel(f"[bold green]所有任务（含挖坟）圆满完成！[/bold green]", border_style="green"))

# --- 辅助函数 (保持不变) ---


def get_valid_user_id() -> str:
    while True:
        uid = Prompt.ask("[cyan]请输入博主的 ID (纯数字)[/cyan]", default="76031078")
        if uid.strip().isdigit():
            return uid.strip()
        rprint("[bold red]❌ ID 必须全是数字！[/bold red]")


def load_config() -> Optional[dict]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None


def save_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def get_auth_data():
    config = load_config()
    data = {}
    if config and "email" in config:
        if Confirm.ask(f"[green]发现已保存账号 ({config['email']})，是否使用？[/green]", default=True):
            data = config
        else:
            data = {}

    if not data:
        if Confirm.ask("[yellow]是否填入账号自动登录？[/yellow]", default=False):
            data["email"] = Prompt.ask("邮箱")
            data["password"] = Prompt.ask("密码", password=True)

    proxy = None
    if config and "proxy" in config:
        if Confirm.ask(f"[green]发现已保存代理 ({config['proxy']})，是否使用？[/green]", default=True):
            proxy = config["proxy"]

    if not proxy:
        if Confirm.ask("[yellow]是否设置 HTTP 代理？[/yellow]", default=False):
            proxy = Prompt.ask("代理地址")

    if Confirm.ask("是否更新本地配置？", default=True):
        new_config = data.copy()
        if proxy:
            new_config["proxy"] = proxy
        save_config(new_config)

    return data, proxy


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    rprint(Panel.fit(
        "[bold magenta]💖 琬琬 OnlyFans 专属下载器 (摸金校尉版) 💖[/bold magenta]", border_style="magenta"))
    user_id = get_valid_user_id()
    auth_data, proxy = get_auth_data()
    rprint("\n[yellow]皇上想要下载什么内容呢？[/yellow]\n1. 📸 仅图片\n2. 🎥 仅视频\n3. 📦 我全都要")
    choice = Prompt.ask("请选择", choices=["1", "2", "3"], default="3")
    mode_map = {"1": "photos", "2": "videos", "3": "all"}

    scraper = WanWanScraper(user_id, mode_map[choice], auth_data, proxy)
    try:
        if scraper.load_cache():
            asyncio.run(scraper.download_all())
        else:
            asyncio.run(scraper.start_scraping())
    except KeyboardInterrupt:
        rprint("\n[bold red]🛑 任务已暂停。[/bold red]")
    except Exception as e:
        rprint(f"\n[bold red]💥 发生意外: {e}[/bold red]")


if __name__ == "__main__":
    main()
