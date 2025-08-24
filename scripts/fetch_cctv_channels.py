#!/usr/bin/env python3
"""
�Զ���ȡIPTV����Ƶ��������M3U�ļ�
������GitHub Actions����
"""

import sys
import os
import time
import re
import subprocess
from datetime import datetime

# �����Ҫ�Ŀ�
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
    print("���ڰ�װ��Ҫ������...")
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
    """�޸��𻵵������"""
    print("�����޸��𻵵������...")
    try:
        result = subprocess.run(["sudo", "apt-get", "update"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"���°��б�ʧ��: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "-f", "install"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"�޸�������ϵʧ��: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "autoremove", "-y"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"�����ʧ��: {result.stderr}")
            return False

        print("������޸����")
        return True

    except Exception as e:
        print(f"�޸������ʱ��������: {e}")
        return False

def install_chrome():
    """��װ Chrome �����"""
    print("���ڰ�װ Chrome �����...")
    try:
        result = subprocess.run([
            "sudo", "wget", "-q", "-O", "-",
            "https://dl.google.com/linux/linux_signing_key.pub"
        ], capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"���� Chrome ��Կʧ��: {result.stderr}")
            return False

        result = subprocess.run([
            "sudo", "sh", "-c",
            "echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list"
        ], capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"��� Chrome �ֿ�ʧ��: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "update"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"���°��б�ʧ��: {result.stderr}")
            return False

        result = subprocess.run(["sudo", "apt-get", "install", "-y", "google-chrome-stable"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"��װ Chrome ʧ��: {result.stderr}")
            return False

        print("Chrome �������װ�ɹ�")
        return True

    except Exception as e:
        print(f"��װ Chrome ʱ��������: {e}")
        return False

def find_chrome_executable():
    """���� Chrome �������ִ���ļ�"""
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
            print(f"�ҵ� Chrome �����: {path}")
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    chrome_version = result.stdout.strip()
                    print(f"Chrome �汾: {chrome_version}")
                    return path
            except Exception as e:
                print(f"��֤ Chrome ��ִ���ļ�ʧ��: {e}")
                continue

    try:
        result = subprocess.run(["which", "google-chrome"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            chrome_path = result.stdout.strip()
            print(f"ʹ�� which �����ҵ� Chrome: {chrome_path}")
            return chrome_path
    except Exception as e:
        print(f"ʹ�� which ������� Chrome ʧ��: {e}")

    return None

def setup_driver():
    """����Chrome�����ѡ�� - ������GitHub Actions"""
    if not fix_broken_packages():
        print("����: �޷��޸��𻵵���������������԰�װ Chrome")

    chrome_path = find_chrome_executable()

    if not chrome_path:
        if not install_chrome():
            raise Exception("�޷���װ Chrome �����")

        chrome_path = find_chrome_executable()
        if not chrome_path:
            raise Exception("Chrome �������װ����δ�ҵ�")

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
    """�Զ���Ⲣ��װ Google Chrome������ Ubuntu��"""
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium"
    ]
    if any(os.path.exists(p) for p in chrome_paths):
        print("Chrome �Ѱ�װ��")
        return True

    print("δ��⵽ Chrome�������Զ���װ Google Chrome ...")
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
        print("Chrome ��װ��ɡ�")
        return True
    except subprocess.CalledProcessError as e:
        print(f"�Զ���װ Chrome ʧ��: {e}")
        return False

if not install_chrome_if_needed():
    print("�޷��Զ���װ Chrome�����ֶ���װ�����ԡ�")
    sys.exit(1)

def find_cctv_channels(driver, base_url):
    """
    ���� iptv-search.com ����ȡ CCTV Ƶ����Ϣ��ץȡǰ20ҳ
    ����: [{'name': 'CCTV-2', 'url': 'http://...'}, ...]
    """
    channels = []
    for page in range(1, 21):
        url = f"{base_url}&page={page}"
        print(f"���ڷ��� {url} ...")
        driver.get(url)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        found = False
        for span in soup.find_all("span", class_="link-text"):
            link = span.get_text(strip=True)
            match = re.search(r'id=(CCTV\d+)', link)
            if match:
                found = True
                name = match.group(1).replace('CCTV', 'CCTV-')
                channels.append({"name": name, "url": link})
                print(f"����Ƶ��: {name} - {link}")
        if not found:
            print(f"��{page}ҳδ����CCTVƵ��")
    return channels

def create_m3u_playlist(channels, filename="cctv_channels.m3u"):
    """����M3U�����б��ļ�"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for channel in channels:
                f.write(f"#EXTINF:-1, {channel['name']}\n")
                f.write(f"{channel['url']}\n")
        print(f"M3U�����б��ѱ��浽 {filename}")
        return True
    except Exception as e:
        print(f"����M3U�ļ�ʱ��������: {e}")
        return False

def main():
    """������"""
    base_url = "https://iptv-search.com/zh-hans/search/?q=CCTV"

    try:
        driver = setup_driver()
        print("? �����������ʼ���ɹ�")
    except Exception as e:
        print(f"? �޷���ʼ�����������: {e}")
        return

    try:
        cctv_channels = find_cctv_channels(driver, base_url)

        if cctv_channels:
            print(f"�ҵ��� {len(cctv_channels)} ��CCTVƵ��")
            success = create_m3u_playlist(cctv_channels)
            if success:
                print("������ɣ�M3U�����б�������")
            else:
                print("����M3U�ļ�ʧ��")
        else:
            print("δ�ҵ�CCTVƵ��")
            with open('page_source.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print("�ѱ���ҳ��Դ���뵽 page_source.html")

    except Exception as e:
        print(f"����ִ�й����з�������: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    main()
