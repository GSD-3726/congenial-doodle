import re
import os
import sys
import time
import random
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

def fetch_page_for_channel(query, page_num=1, max_retries=3):
    """为单个频道获取页面内容。每个线程独立运行此函数，内部创建自己的浏览器实例"""
    for attempt in range(max_retries):
        try:
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
            
            # 添加随机User-Agent和更多请求头
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
            ]
            
            context = browser.new_context(
                java_script_enabled=True,  # 启用JavaScript，有些网站需要
                user_agent=random.choice(user_agents),
                accept_downloads=False,  # 禁用下载处理
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                    'Referer': 'https://iptvs.hacks.tools/'
                }
            )
            
            try:
                page_obj = context.new_page()
                # 设置默认导航超时时间
                page_obj.set_default_navigation_timeout(60000)
                page_obj.set_default_timeout(30000)
                
                # 拦截不必要的资源请求以提高加载速度
                def route_handler(route):
                    resource_type = route.request.resource_type
                    if resource_type in ['image', 'stylesheet', 'font', 'media']:
                        route.abort()
                    else:
                        route.continue_()
                
                # 注册路由处理器
                page_obj.route("**/*", route_handler)
                
                url = f"https://iptvs.hacks.tools/?q={quote(query)}&page={page_num}"
                
                # 添加随机延迟，避免请求过于频繁
                time.sleep(random.uniform(1, 3))
                
                # 使用更宽松的等待条件
                response = page_obj.goto(url, timeout=60000, wait_until='domcontentloaded')
                if not response or response.status != 200:
                    print(f"请求失败 (尝试 {attempt+1}/{max_retries}): {url}, 状态码: {getattr(response, 'status', '无响应')}")
                    continue
                    
                # 等待表格出现，使用更灵活的选择器
                try:
                    # 尝试等待表格加载
                    page_obj.wait_for_selector('table', timeout=10000)
                except:
                    # 如果表格选择器失败，尝试等待页面完全加载
                    try:
                        page_obj.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        # 如果还是失败，等待一段时间再继续
                        time.sleep(2)
                
                # 获取页面内容
                content = page_obj.content()
                return content
            except Exception as e:
                print(f"在处理 {query} 第 {page_num} 页时发生异常 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    # 等待一段时间再重试
                    time.sleep(random.uniform(2, 5))
                    continue
                return None
            finally:
                # 确保关闭上下文和浏览器
                context.close()
                browser.close()
        except Exception as e:
            print(f"浏览器启动异常 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(2, 5))
                continue
            return None
        finally:
            playwright.stop()  # 停止playwright
    
    return None

def extract_links(html, channel):
    """优化后的链接提取（使用html.parser替代lxml）"""
    if not html:
        return []
    
    # 修改此处：使用html.parser替代lxml，避免安装依赖
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    
    # 查找所有表格行
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2:
            continue
            
        current_channel = cells[0].get_text(strip=True)
        # 使用更宽松的匹配条件
        if channel.lower() in current_channel.lower():
            for link in row.find_all('a', href=True):
                href = link['href']
                if '.m3u8' in href:
                    # 修复可能的拼写错误：hhref -> href
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
            
        # 页面间添加随机延迟
        time.sleep(random.uniform(1, 2))
        
    return all_links

def main():
    try:
        channels = [
            "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV6", "CCTV7", "CCTV8", 
            "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16","湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视", 
        "广东卫视", "深圳卫视", "安徽卫视", "黑龙江卫视", "辽宁卫视"
        ]
        
        all_links = []
        # 减少线程数以避免过多并发请求
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 直接提交频道处理任务，每个任务内部会管理自己的浏览器实例
            future_to_channel = {executor.submit(process_channel, ch): ch for ch in channels}
            for future in future_to_channel:
                try:
                    result = future.result()
                    if result:
                        all_links.extend(result)
                        print(f"成功获取 {len(result)} 个 {future_to_channel[future]} 的链接")
                    else:
                        print(f"未获取到 {future_to_channel[future]} 的链接")
                except Exception as e:
                    print(f"处理频道 {future_to_channel[future]} 时发生错误: {e}")
        
        # 生成 M3U 文件
        if all_links:
            # 去重并保留第一个出现的链接
            seen_urls = set()
            unique_links = []
            for item in all_links:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_links.append(item)
            
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
            # 创建一个空的live.m3u文件
            with open(output_dir/"live.m3u", 'w') as f:
                f.write("#EXTM3U\n")
    except Exception as e:
        print(f"主程序执行出错: {e}")
        # 即使出错，也确保output目录存在
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        # 创建一个空的live.m3u文件
        with open(output_dir/"live.m3u", 'w') as f:
            f.write("#EXTM3U\n")
        sys.exit(1)  # 退出码1表示错误

if __name__ == "__main__":
    if not install_playwright():
        main()
