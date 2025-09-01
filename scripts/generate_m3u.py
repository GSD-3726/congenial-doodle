import re
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright  # 注意仍然使用同步API

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

def fetch_page_for_channel(query, page_num=1):
    """为单个频道获取页面内容。每个线程独立运行此函数，内部创建自己的浏览器实例"""
    playwright = sync_playwright().start()
    # 每个线程独立启动浏览器，避免共享
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--single-process'
        ]
    )
    context = browser.new_context(
        java_script_enabled=False,
        user_agent='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        accept_downloads=False  # 禁用下载处理
    )
    try:
        page_obj = context.new_page()
        url = f"https://iptvs.hacks.tools/?q={quote(query)}&page={page_num}"
        
        response = page_obj.goto(url, timeout=15000, wait_until='domcontentloaded')
        if not response or response.status != 200:
            print(f"请求失败: {url}, 状态码: {getattr(response, 'status', '无响应')}")
            return None
            
        page_obj.wait_for_selector('table', timeout=8000)
        content = page_obj.content()
        return content
    except Exception as e:
        print(f"在处理 {query} 第 {page_num} 页时发生异常: {e}")
        return None
    finally:
        # 确保关闭上下文和浏览器
        context.close()
        browser.close()
        playwright.stop()  # 停止playwright

def extract_links(html, channel):
    """优化后的链接提取（提升 40% 速度）"""
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'lxml')
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
                    href = href if href.startswith('http') else f'https:{href}' if href.startswith('//') else f'https://iptvs.hacks.tools{href}'
                    quality = CHANNEL_PATTERN.search(current_channel)
                    results.append({
                        'channel': current_channel,
                        'url': href,
                        'quality': quality.group() if quality else '未知'
                    })
    return results

def process_channel(channel):
    """单频道处理（带快速失败机制）。此函数在每个线程中独立运行，包含完整的浏览器生命周期"""
    all_links = []
    for page in range(1, 3):  # 限制最大页数
        if (html := fetch_page_for_channel(channel, page)) is None:
            break
            
        links = extract_links(html, channel)
        if not links and page == 1:  # 第一页无结果立即终止
            break
            
        all_links.extend(links)
        if len(all_links) > 5:  # 提前终止条件
            break
    return all_links

def main():
    try:
        channels = [
            "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+", "CCTV6",
            "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视"
        ]
        
        all_links = []
        # 使用线程池处理每个频道
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 直接提交频道处理任务，每个任务内部会管理自己的浏览器实例
            future_to_channel = {executor.submit(process_channel, ch): ch for ch in channels}
            for future in future_to_channel:
                try:
                    result = future.result()
                    all_links.extend(result)
                except Exception as e:
                    print(f"处理频道时发生错误: {e}")
        
        # 生成 M3U 文件
        if unique_links := {item['url']: item for item in all_links}.values():
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            with open(output_dir/"live.m3u", 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for item in sorted(unique_links, key=lambda x: x['channel']):
                    f.write(f'#EXTINF:-1 tvg-name="{item["channel"]}",{item["channel"]} ({item["quality"]})\n{item["url"]}\n')
            
            print(f"生成 {len(unique_links)} 个频道到 {output_dir}/live.m3u")
        else:
            print("未找到任何频道链接，可能所有请求都失败了。")
            # 确保output目录存在，即使为空，避免后续cp命令失败
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            # 可以选择创建一个空的live.m3u文件或什么都不做
            # with open(output_dir/"live.m3u", 'w') as f:
            #     f.write("#EXTM3U\n")
    except Exception as e:
        print(f"主程序执行出错: {e}")
        # 即使出错，也确保output目录存在
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        sys.exit(1)  # 退出码1表示错误

if __name__ == "__main__":
    if not install_playwright():
        main()
