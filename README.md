<div align="center">

# 👑 Royal OnlyFans Downloader Pro

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Stealth-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev/)
[![Rich](https://img.shields.io/badge/UI-Rich%20CLI-purple?style=for-the-badge&logo=charm&logoColor=white)](https://github.com/Textualize/rich)
[![License](https://img.shields.io/badge/License-UNLICENSE-yellow?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](./LICENSE)
[![Status](https://img.shields.io/badge/Status-DRM%20Hunter-red?style=for-the-badge&logo=shield&logoColor=white)]()

**既然付了费，所有的曼妙理应为您私有：全自动 DRM 破防归档神器**
<br>
*If you paid for it, you own it. The ultimate media scraper bypassing DRM with imperial precision.*

[📖 简介](#intro) • [✨ 特性](#features) • [🛠️ 核心配置(必读)](#prerequisites) • [💻 安装](#installation) • [🚀 使用](#usage)

</div>

---

## <a id="intro"></a>📖 简介 | Introduction

这是一个基于 **Python** 的工业级爬虫工具，专为捍卫“付费用户”的数字主权而生。它彻底粉碎了流媒体平台的封闭限制，不仅能秒杀常规图片，更能通过强大的 **DRM 猎杀引擎 (Hunter Engine)** 攻克 Widevine 加密。

无需繁琐抓包，无需手动计算。脚本接管系统浏览器，模拟真实用户行为，将那些“镜中花水中月”的加密视频与音频，实实在在地永久保存到您的硬盘中。

## <a id="features"></a>✨ 皇室特性 | Key Features

*   **🎙️ 全媒体收割**：深度支持 **图片 (Photos)**、**视频 (Videos)** 以及 **音频 (Audios)** 资源的全量采集。
*   **🔓 DRM 降维打击**：
    *   内置 **CDM (Content Decryption Module)** 调用逻辑。
    *   配合 `device.wvd` 实现全自动 PSSH 提取、Challenge 注入与密钥猎取。
    *   支持拦截真实流量（Traffic Interception）进行重放攻击，无视签名算法更新。
*   **⚡ 极速异步并发**：采用 `asyncio` + `httpx` 架构，支持 50+ 线程同时运作，极速搬运。
*   **🕵️‍♂️ 隐身持久化**：
    *   使用 `launch_persistent_context` 接管系统 Chrome，保留登录状态（Cookie），避免重复登录。
    *   彻底抹除自动化痕迹，通过 JS 注入伪装，绕过反爬检测。
*   **💾 智能缓存 & 归档**：
    *   本地缓存抓取列表。支持断点续传，一键复用缓存。
    *   下载完成后自动生成详细的 `manifest.json` 资产清单。
*   **⚙️ 皇室配置管家**：内置交互式 CLI 设置向导 (`s` 指令)，轻松管理路径、代理与并发参数。

## <a id="prerequisites"></a>🛠️ 核心配置 | The Royal Arsenal (Required)

要实现全自动爆破与抓取，您必须准备以下“四大神器”。**缺一不可：**

### 1. 正版 Google Chrome (浏览器真身)
*   **必要性**：Playwright 自带的 Chromium 通常阉割了 Widevine 组件，无法处理 DRM。必须调用系统安装的 **正式版 Chrome**。
*   **配置**：脚本会自动尝试识别路径。如果失败，请在 CLI 设置 (`s`) 中手动填入 `chrome.exe` 的绝对路径。

### 2. device.wvd (解密私钥)
*   **必要性**：这是模拟安卓设备与 License Server 通信的核心凭证。
*   **获取**：请自行通过安卓手机提取或从可信渠道获取 L3 CDM 的 `device.wvd` 文件。
*   **配置**：将文件重命名为 `device.wvd` 并放置在脚本**根目录**下。

### 3. N_m3u8DL-RE (下载核心)
*   **作用**：负责下载加密的 DASH/HLS 流媒体，并调用解密工具。
*   **获取**：[N_m3u8DL-RE Releases](https://github.com/nilaoda/N_m3u8DL-RE/releases)
*   **配置**：解压后，请在 CLI 设置中配置该工具的可执行路径（推荐放入环境变量）。

### 4. mp4decrypt (解密手术刀)
*   **作用**：由 N_m3u8DL-RE 自动调用，负责将加密数据还原为 MP4。
*   **获取**：[Bento4 SDK Downloads](https://www.bento4.com/downloads/)
*   **配置**：请务必将 `bin` 目录下的 `mp4decrypt` 添加到系统的 **环境变量 (PATH)** 中。

## <a id="installation"></a>💻 安装步骤 | Installation

1.  **克隆仓库**
    ```bash
    git clone https://github.com/TianLanDaoRen/RoyalOnlyFansDownloader.git
    cd RoyalOnlyFansDownloader
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```
    *如果未提供 requirements.txt，请运行：*
    ```bash
    pip install playwright httpx[socks] rich aiofiles pywidevine pyyaml protobuf
    ```

## <a id="usage"></a>🚀 使用方法 | Usage

1.  **起驾**：
    ```bash
    python main.py
    ```

2.  **内务调整 (首次运行)**：
    *   输入 `s` 进入配置中心。
    *   检查并配置 **Chrome 路径**、**代理地址 (Proxy)** 及 **RE 工具路径**。
    *   配置会自动保存至 `wanwan_config.json`。

3.  **开始收割**：
    *   输入博主 ID。
    *   选择模式（推荐 `4. 我全都要`）。
    *   **登录**：脚本会启动隐身浏览器，请在弹出的窗口中登录 OnlyFans（首次需登录，后续自动保持）。
    *   **静候佳音**：脚本将自动扫描、下载、猎杀 DRM 密钥并解密。

4.  **缓存复用**：
    *   若程序中断，再次运行并检测到缓存时，选择 `Yes` 可跳过扫描，直接进行下载和解密。

## <a id="output"></a>📂 输出结构 | Output

```text
Royal_OnlyFans_Collection/
└── {user_id}/
    ├── 123456_99999-Sweet_Voice.mp3     # 🎵 音频
    ├── [DRM]_223344_88888-Full_HD.mp4   # 🎥 自动解密的视频
    ├── 334455_77777-Selfie.jpg          # 📸 图片
    └── manifest_20260110.json           # 📜 资产清单
```

## <a id="disclaimer"></a>⚠️ 免责声明 | Disclaimer

本工具仅供**技术研究与个人学习**使用。
*   请尊重创作者版权，严禁将抓取内容用于商业传播或非法分发。
*   用户需自行承担使用本工具产生的一切法律后果。
*   **Use at your own risk.**

---

<div align="center">
    Made with ❤️ by <b>Wanwan</b> for <b>Yunsi</b>
    <br>
    <br>
    <i>"Sovereignty over every pixel is the absolute right of the patron;<br>what is acquired by lawful exchange shall be preserved in perpetuity."</i>
</div>