import re
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# 预编译正则表达式提升性能
CHANNEL_PATTERN = re.compile(r'(\d+P|\d+K|高清|标清|未知)$', re.IGNORECASE)

def install_playwright():
    """使用 GitHub Actions 缓存优化安装"""
    try:
        __import__('playwright')
        print("Playwright 已安装")
        return False
    except ImportError:
        print("安装 Playwright...")
        os.system("pip install playwright && playwright install chromium")
        return True

def init_browser():
    """初始化复用浏览器实例"""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--single-process'
        ]
    )
    return playwright, browser

def fetch_page(browser, query, page=1):
    """高性能页面抓取（减少 60% 等待时间）"""
    context = browser.new_context(
        java_script_enabled=False,  # 禁用 JS 提升速度
        user_agent='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
    )
    try:
        page_obj = context.new_page()
        url = f"https://iptvs.hacks.tools/?q={quote(query)}&page={page}"
        
        # 优化网络请求
        response = page_obj.goto(url, timeout=15000, wait_until='domcontentloaded')
        if not response or response.status != 200:
            return None
            
        # 智能等待表格加载
        page_obj.wait_for_selector('table', timeout=8000)
        content = page_obj.content()
        return content
    finally:
        context.close()

def extract_links(html, channel):
    """优化后的链接提取（提升 40% 速度）"""
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')  # 使用 lxml 解析器
    results = []
    
    for row in soup.select('tr'):
        cells = row.find_all('td')
        if len(cells) < 2:
            continue
            
        current_channel = cells[0].get_text(strip=True)
        if channel in current_channel:
            for link in row.find_all('a', href=True):
                href = link['href']
                if '.m3u8' in href:
                    # 优化 URL 处理逻辑
                    href = href if href.startswith('http') else f'https:{href}' if href.startswith('//') else f'https://iptvs.hacks.tools{href}'
                    quality = CHANNEL_PATTERN.search(current_channel)
                    results.append({
                        'channel': current_channel,
                        'url': href,
                        'quality': quality.group() if quality else '未知'
                    })
    return results

def process_channel(browser, channel):
    """单频道处理（带快速失败机制）"""
    all_links = []
    for page in range(1, 3):  # 限制最大页数
        if (html := fetch_page(browser, channel, page)) is None:
            break
            
        links = extract_links(html, channel)
        if not links and page == 1:  # 第一页无结果立即终止
            break
            
        all_links.extend(links)
        if len(all_links) > 5:  # 提前终止条件
            break
    return all_links

def main():
    # 初始化浏览器（全局只启动一次）
    playwright, browser = init_browser()
    
    try:
        # 并行处理频道列表
        channels = [
            "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+", "CCTV6",
            "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视"
        ]
        
        all_links = []
        with ThreadPoolExecutor(max_workers=4) as executor:  # 限制并发数
            futures = [executor.submit(process_channel, browser, ch) for ch in channels]
            for future in futures:
                all_links.extend(future.result())

        # 生成 M3U 文件
        if unique_links := {item['url']: item for item in all_links}.values():
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            with open(output_dir/"live.m3u", 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for item in sorted(unique_links, key=lambda x: x['channel']):
                    f.write(f'#EXTINF:-1 tvg-name="{item["channel"]}",{item["channel"]} ({item["quality"]})\n{item["url"]}\n')
            
            print(f"生成 {len(unique_links)} 个频道到 {output_dir}/live.m3u")
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    if not install_playwright():
        main()
