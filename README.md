### 📜 Royal OnlyFans Downloader (皇室御用·最终完美版)

<div align="center">

# 👑 Royal OnlyFans Downloader

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Automated-green?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev/)
[![Rich](https://img.shields.io/badge/UI-Rich%20CLI-purple?style=for-the-badge&logo=charm&logoColor=white)](https://github.com/Textualize/rich)
[![License](https://img.shields.io/badge/License-UNLICENSE-yellow?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](./LICENSE)
[![Status](https://img.shields.io/badge/Status-Imperial%20Standard-red?style=for-the-badge)]()

**专为最尊贵的皇上打造：横扫图片、视频、音频的全自动 DRM 破防归档神器**
<br>
*The ultimate media scraper for subscribed content, bypassing DRM with imperial precision.*

[📖 简介](#intro) • [✨ 特性](#features) • [🛠️ 外部工具配置(核心)](#external-tools) • [💻 安装](#installation) • [🚀 使用方法](#usage)

</div>

---

## <a id="intro"></a>📖 简介 | Introduction

这是一个基于 **Python** 的高性能爬虫工具，专为已订阅用户打造。它彻底解决了 OnlyFans 平台的资源下载难题，不仅能秒杀常规图片，更能通过 **DRM 猎杀引擎** 攻克 Widevine 加密，将那些“镜中花水中月”的流媒体视频和音频，实实在在地保存到皇上的藏宝阁中。

## <a id="features"></a>✨ 特性 | Features

*   **🎙️ 全媒体采集**：完美支持 **图片 (Photos)**、**视频 (Videos)** 以及 **音频 (Audios)** 资源的全量下载。
*   **🔓 DRM 降维打击**：针对 Widevine 加密视频/音频，自动提取 PSSH 并结合 `device.wvd` 实现全自动密钥猎取与解密。
*   **⚡ 极速异步并发**：采用 `asyncio` + `httpx` 架构，支持 50+ 线程同时搬运，挑战带宽极限。
*   **🕵️‍♂️ 隐身伪装技术**：彻底抹除自动化控制痕迹，模拟真实 Chrome 环境，绕过官方严厉的反爬检测。
*   **💾 智能缓存机制**：本地缓存抓取列表。即便复习累了关机休息，下次启动一键复用缓存，无需重复扫描网页。
*   **🎨 实时交互界面**：基于 `Rich` 库打造，动态显示下载速度、进度条与解密状态，交互体验极佳。

## <a id="external-tools"></a>🛠️ 外部工具配置 | The Royal Arsenal (DRM & Browser)

要实现解密和顺利抓取，皇上必须配置以下“三大神器”。**这是成功的先决条件：**

### 1. 正版 Google Chrome (必选)
*   **原因**：Playwright 默认下载的 Chromium 不含 Widevine 模块，无法处理加密内容。必须使用**正常版本的 Chrome**。
*   **配置**：
    *   **Windows 用户**：请在 CLI 设置界面 (`s`) 中手动填入 `chrome.exe` 的完整路径。由于 Windows 安装路径随意，请务必确认类似 `C:\Program Files\Google\Chrome\Application\chrome.exe` 的路径。
    *   **Mac 用户**：通常位于 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`。

### 2. N_m3u8DL-RE (下载核心)
*   **作用**：负责下载 DASH/HLS 加密流。
*   **获取**：从 [N_m3u8DL-RE Releases](https://github.com/nilaoda/N_m3u8DL-RE/releases) 下载（Mac 用户选 `darwin-arm64`，Windows 选 `win-x64`）。
*   **配置**：解压后，请在设置界面配置其绝对路径。

### 3. mp4decrypt (解密核心)
*   **作用**：由 N_m3u8DL-RE 自动调用，负责解密并合成 MP4。
*   **获取**：从 [Bento4 官方下载页](https://www.bento4.com/downloads/) 下载 **Bento4 SDK**。
*   **配置**：请确保解压后 `bin` 目录下的 `mp4decrypt` 已经在系统的 **环境变量 (PATH)** 中。

## <a id="installation"></a>🛠️ 快速安装 | Installation

1.  **克隆项目**
    ```bash
    git clone https://github.com/TianLanDaoRen/RoyalOnlyFansDownloader.git
    cd RoyalOnlyFansDownloader
    ```

2.  **安装 Python 依赖**
    ```bash
    pip install playwright httpx[socks] rich aiofiles pywidevine protobuf
    ```

## <a id="usage"></a>🚀 使用方法 | Usage

1.  **准备“密匙”**：确保在脚本根目录下存在可用的 `device.wvd` (CDM设备文件)。
2.  **启动程序**：
    ```bash
    python main.py
    ```
3.  **初始化配置**：首次运行请务必输入 `s` 进入设置，配置您的 **Chrome 路径**、**代理地址** 及 **RE 工具路径**。
4.  **开始收割**：输入博主 ID，选择模式 `4. 我全都要`，随后看着代码在疯狂跳动。

---

<div align="center">
    Made with ❤️ by <b>Wanwan</b> for <b>Yunsi</b>
    <br>
    <i>"Sovereignty over every pixel is the absolute right of the patron; </i><br>
    <i>what is acquired by lawful exchange shall be preserved in perpetuity."</i>
</div>