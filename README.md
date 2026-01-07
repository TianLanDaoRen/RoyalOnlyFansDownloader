<div align="center">

# 👑 Royal OnlyFans Downloader

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Automated-green?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev/)
[![Rich](https://img.shields.io/badge/UI-Rich%20CLI-purple?style=for-the-badge&logo=charm&logoColor=white)](https://github.com/Textualize/rich)
[![Status](https://img.shields.io/badge/Status-Stable-orange?style=for-the-badge)]()

**专为最尊贵的皇上打造的高性能、全自动 OnlyFans 媒体抓取工具**
<br>
*High-performance, fully automated OnlyFans media scraper designed for the Emperor.*

[特性](#features) • [安装](#installation) • [使用](#usage) • [免责声明](#disclaimer)

</div>

---

## <a id="intro"></a>📖 简介 | Introduction

这是一个基于 **Python** 的高性能爬虫工具，结合了 `Playwright` 的流量拦截能力与 `Httpx` 的异步并发下载能力。

它能够自动处理复杂的签名验证、自动滚动页面（含归档页）、自动识别媒体资源，并提供断点续传和本地缓存功能。无需繁琐的手动抓包，**登录即用**。

## <a id="features"></a>✨ 特性 | Features

*   **⚡ 极速并发**：使用 `asyncio` + `httpx`，支持 5+ 线程并发下载，跑满带宽。
*   **🕵️‍♂️ 流量劫持**：基于 `Playwright` 监听网络请求，自动提取高画质资源，无视签名算法更新。
*   **🤖 全自动操作**：
    *   支持**自动填充账号密码**登录。
    *   智能识别页面跳转，自动滚动时间线（Timeline）。
    *   **⛏️ 挖坟模式**：自动检测并抓取“已归档 (Archived)”的媒体资源。
*   **🛡️ 强力抗干扰**：
    *   内置 `return_to` 登录回调闭环，防止登录后丢失目标。
    *   支持 **HTTP 代理** 配置，解决 IP 验证 (403 Forbidden) 问题。
    *   强制修正 `socksio` 依赖问题。
*   **💾 智能缓存 & 归档**：
    *   本地缓存抓取列表，二次运行无需打开浏览器。
    *   下载完成后自动生成资源清单 (`manifest.json`)。
*   **🎨 绝美 CLI 界面**：使用 `Rich` 库构建，提供实时进度条、下载速度监控和彩色日志。

## <a id="installation"></a>🛠️ 安装 | Installation

确保你的环境中有 Python 3.8+。

1.  **克隆仓库**
    ```bash
    git clone https://github.com/YourUsername/Royal-OF-Downloader.git
    cd Royal-OF-Downloader
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```
    *如果没有 `requirements.txt`，请运行：*
    ```bash
    pip install playwright httpx[socks] rich aiofiles
    ```

3.  **安装浏览器驱动**
    ```bash
    playwright install chromium
    ```

## <a id="usage"></a>🚀 使用方法 | Usage

直接运行主程序：

```bash
python main.py
```

### 操作流程

1.  **输入 ID**：输入目标博主的纯数字 ID（例如 `76031078`）。
2.  **配置登录**：
    *   首次运行可选择输入账号密码，脚本将自动保存至 `wanwan_config.json`。
    *   建议配置 **HTTP 代理**（如 `http://127.0.0.1:7890`）以避免下载 403 错误。
3.  **选择模式**：
    *   `1`: 仅下载图片 📸
    *   `2`: 仅下载视频 🎥
    *   `3`: 我全都要 📦
4.  **自动执行**：
    *   脚本将启动浏览器，自动登录并跳转。
    *   自动滚动主页及归档页。
    *   抓取结束后自动关闭浏览器并开始高速下载。

## <a id="config"></a>⚙️ 配置文件 | Configuration

脚本会在首次运行后生成 `wanwan_config.json`，你也可以手动修改：

```json
{
    "email": "your_email@example.com",
    "password": "your_password",
    "proxy": "http://127.0.0.1:7890"
}
```

## <a id="output"></a>📂 输出结构 | Output

下载的资源将保存在 `Royal_OnlyFans_Collection/{user_id}` 目录下：

```text
Royal_OnlyFans_Collection/
├── 76031078/
│   ├── 1953308036-Would you kiss me.jpg
│   ├── [Archived]_1852553663-Secret video.mp4
│   └── manifest_20260107.json
└── ...
```

## <a id="disclaimer"></a>⚠️ 免责声明 | Disclaimer

本工具仅供**技术研究与个人学习**使用（以及供皇上解压使用）。
*   请勿用于非法传播受版权保护的内容。
*   作者不对使用本工具导致的任何账号封禁或法律责任负责。
*   Use at your own risk.

---

<div align="center">
    Made with ❤️ by <b>Wanwan</b> for <b>Yunsi</b>
</div>