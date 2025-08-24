#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动获取IPTV央视频道并生成M3U文件
适用于GitHub Actions环境
"""

import sys
import os
import time
import re
import subprocess
from datetime import datetime

# 导入必要的库
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.common.keys import Keys
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("正在安装必要的依赖...")
    os.system(f"{sys.executable} -m pip install selenium webdriver-manager requests beautifulsoup4")
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.common.keys import Keys
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    import requests
    from bs4 import BeautifulSoup

def fix_broken_packages():
    """修复损坏的软件包"""
    print("尝试修复损坏的软件包...")
    try:
        result = subprocess.run(["sudo", "apt-get", "update"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"更新包列表失败: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "-f", "install"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"修复依赖关系失败: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "autoremove", "-y"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"清理包失败: {result.stderr}")
            return False

        print("软件包修复完成")
        return True

    except Exception as e:
        print(f"修复软件包时发生错误: {e}")
        return False

def install_chrome():
    """安装 Chrome 浏览器"""
    print("正在安装 Chrome 浏览器...")
    try:
        result = subprocess.run([
            "sudo", "wget", "-q", "-O", "-",
            "https://dl.google.com/linux/linux_signing_key.pub"
        ], capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"下载 Chrome 密钥失败: {result.stderr}")
            return False

        result = subprocess.run([
            "sudo", "sh", "-c",
            "echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list"
        ], capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"添加 Chrome 仓库失败: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "update"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"更新包列表失败: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "install", "-y", "google-chrome-stable"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"安装 Chrome 失败: {result.stderr}")
            return False

        print("Chrome 浏览器安装成功")
        return True

    except Exception as e:
        print(f"安装 Chrome 时发生错误: {e}")
        return False

def find_chrome_executable():
    """查找 Chrome 浏览器可执行文件"""
    possible_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
        "/opt/google/chrome/google-chrome",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"找到 Chrome 浏览器: {path}")
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    chrome_version = result.stdout.strip()
                    print(f"Chrome 版本: {chrome_version}")
                    return path
            except Exception as e:
                print(f"验证 Chrome 可执行文件失败: {e}")
                continue

    try:
        result = subprocess.run(["which", "google-chrome"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            chrome_path = result.stdout.strip()
            print(f"使用 which 命令找到 Chrome: {chrome_path}")
            return chrome_path
    except Exception as e:
        print(f"使用 which 命令查找 Chrome 失败: {e}")

    return None

def setup_driver():
    """设置Chrome浏览器选项 - 适用于GitHub Actions"""
    if not fix_broken_packages():
        print("警告: 无法修复损坏的软件包，继续尝试安装 Chrome")

    chrome_path = find_chrome_executable()

    if not chrome_path:
        if not install_chrome():
            raise Exception("无法安装 Chrome 浏览器")

        chrome_path = find_chrome_executable()
        if not chrome_path:
            raise Exception("Chrome 浏览器安装后仍未找到")

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    chrome_options.binary_location = chrome_path

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def install_chrome_if_needed():
    """自动检测并安装 Google Chrome（仅限 Ubuntu）"""
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium"
    ]
    if any(os.path.exists(p) for p in chrome_paths):
        print("Chrome 已安装。")
        return True

    print("未检测到 Chrome，正在自动安装 Google Chrome ...")
    try:
        subprocess.run(
            "wget -O- https://dl.google.com/linux/linux_signing_key.pub | "
            "sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg",
            shell=True, check=True
        )
        subprocess.run(
            "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] "
            "http://dl.google.com/linux/chrome/deb/ stable main' | "
            "sudo tee /etc/apt/sources.list.d/google-chrome.list",
            shell=True, check=True
        )
        subprocess.run("sudo apt update", shell=True, check=True)
        subprocess.run("sudo apt install -y google-chrome-stable", shell=True, check=True)
        print("Chrome 安装完成。")
        return True
    except subprocess.CalledProcessError as e:
        print(f"自动安装 Chrome 失败: {e}")
        return False

if not install_chrome_if_needed():
    print("无法自动安装 Chrome，请手动安装后重试。")
    sys.exit(1)

def find_cctv_channels(driver, base_url):
    """
    访问 iptv-search.com 并提取 CCTV 频道信息，抓取前20页
    返回: [{'name': 'CCTV-2', 'url': 'http://...'}, ...]
    """
    channels = []
    for page in range(1, 31):
        url = f"{base_url}&page={page}"
        print(f"正在访问 {url} ...")
        driver.get(url)
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        found = False
        for span in soup.find_all("span", class_="link-text"):
            link = span.get_text(strip=True)
            match = re.search(r'id=(CCTV\d+)', link)
            if match:
                found = True
                name = match.group(1).replace('CCTV', 'CCTV-')
                channels.append({"name": name, "url": link})
                print(f"发现频道: {name} - {link}")
        if not found:
            print(f"第{page}页未发现CCTV频道")
    return channels

def create_m3u_playlist(channels, filename="cctv_channels.m3u"):
    """创建M3U播放列表文件"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for channel in channels:
                f.write(f"#EXTINF:-1, {channel['name']}\n")
                f.write(f"{channel['url']}\n")
        print(f"M3U播放列表已保存到 {filename}")
        return True
    except Exception as e:
        print(f"创建M3U文件时发生错误: {e}")
        return False

def main():
    """主函数"""
    base_url = "https://iptv-search.com/zh-hans/search/?q=CCTV"

    try:
        driver = setup_driver()
        print("? 浏览器驱动初始化成功")
    except Exception as e:
        print(f"? 无法初始化浏览器驱动: {e}")
        return

    try:
        cctv_channels = find_cctv_channels(driver, base_url)

        if cctv_channels:
            print(f"找到了 {len(cctv_channels)} 个CCTV频道")
            success = create_m3u_playlist(cctv_channels)
            if success:
                print("操作完成！M3U播放列表已生成")
            else:
                print("创建M3U文件失败")
        else:
            print("未找到CCTV频道")
            with open('page_source.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print("已保存页面源代码到 page_source.html")

    except Exception as e:
        print(f"程序执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    main()


