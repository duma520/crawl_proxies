# Version 40

import requests
from bs4 import BeautifulSoup
import time
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import urllib3
import re
import os
import random
import subprocess
import sys
from fake_useragent import UserAgent
from fake_headers import Headers
import queue
import threading
from threading import Thread, Lock
import json
from collections import defaultdict

# 初始化 UserAgent 和 Headers 对象
ua = UserAgent()
headers_faker = Headers(
    browser="chrome",
    os="win",
    headers=True
)

# 线程监控相关
thread_monitor_enabled = False
thread_stats = defaultdict(dict)
thread_stats_lock = Lock()

# 生成随机的 User-Agent 和请求头
def get_random_user_agent():
    return ua.random

def get_random_headers():
    headers = headers_faker.generate()
    return headers

# 设置请求头，模拟浏览器访问
headers = get_random_headers()

# 检查代理格式是否有效
def is_valid_proxy(proxy):
    proxy_pattern = re.compile(r'^(http://|https://|socks5://)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$')
    match = proxy_pattern.match(proxy)
    if not match:
        return False

    ip = match.group(2)
    port = match.group(3)
    return is_valid_ip(ip) and is_valid_port(port)

def is_valid_ip(ip):
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False
        except ValueError:
            return False
    return True

def is_valid_port(port):
    try:
        port_num = int(port)
        if 1 <= port_num <= 65535:
            return True
    except ValueError:
        pass
    return False

# 验证代理IP是否可用
def validate_proxy(proxy, verify_url, timeout=10, verify_ssl=False):
    if thread_monitor_enabled:
        with thread_stats_lock:
            thread_stats[threading.current_thread().name] = {
                'status': 'validating',
                'proxy': proxy,
                'start_time': time.time()
            }
    
    if not is_valid_proxy(proxy):
        logging.warning(f"代理 {proxy} 格式无效。")
        return None, None, False

    prefixes = ['http://', 'https://', 'socks5://']
    for prefix in prefixes:
        try:
            formatted_proxy = f"{prefix}{proxy.split('://')[-1]}"
            proxies = {
                'http': formatted_proxy,
                'https': formatted_proxy
            }
            start_time = time.time()
            response = requests.get(verify_url, headers=get_random_headers(), proxies=proxies, timeout=timeout, verify=verify_ssl)
            end_time = time.time()
            if response.status_code == 200:
                latency = end_time - start_time
                logging.info(f"代理 {formatted_proxy} 有效。响应时间: {latency:.2f}秒")
                return formatted_proxy, latency, True
        except requests.exceptions.ProxyError as e:
            logging.warning(f"代理 {formatted_proxy} 无效: {e}")
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"代理 {formatted_proxy} 无效: {e}")
        except Exception as e:
            logging.warning(f"代理 {formatted_proxy} 无效: {e}")
    
    if thread_monitor_enabled:
        with thread_stats_lock:
            thread_stats[threading.current_thread().name]['status'] = 'idle'
    return None, None, False

# 获取代理IP的函数
def get_proxies_from_url(url, table_id=None, ip_index=0, port_index=1, proxy_type_index=None, proxy=None, show=False, show_invalid=False, verbose=False, interval=2, request_timeout=10):
    if thread_monitor_enabled:
        with thread_stats_lock:
            thread_stats[threading.current_thread().name] = {
                'status': 'crawling',
                'url': url,
                'start_time': time.time()
            }
    
    time.sleep(random.uniform(interval, interval + 2))
    try:
        proxies = None
        if proxy:
            if proxy.startswith('socks5'):
                proxies = {'http': proxy, 'https': proxy}
            else:
                proxies = {'http': proxy, 'https': proxy}

        auth = None
        if proxy and '@' in proxy:
            auth = proxy.split('@')[0]
            proxy = proxy.split('@')[1]
            proxies = {
                'http': f"http://{auth}@{proxy}",
                'https': f"http://{auth}@{proxy}"
            }

        headers = get_random_headers()
        time.sleep(interval)
        time.sleep(random.uniform(interval, interval + 2))

        response = requests.get(url, headers=headers, proxies=proxies, timeout=request_timeout, verify=False)
        response.raise_for_status()

        if verbose:
            print(response.text)

        soup = BeautifulSoup(response.text, 'html.parser')
        proxies_list = []
        
        table = soup.find('table', {'id': table_id}) if table_id else soup.find('table')
        if table:
            for row in table.find_all('tr')[1:]:
                columns = row.find_all('td')
                if len(columns) > max(ip_index, port_index):
                    ip = columns[ip_index].text.strip()
                    port = columns[port_index].text.strip()
                    ip = re.sub(r'[^0-9.]', '', ip)
                    port = re.sub(r'[^0-9]', '', port)
                    if ip and port:
                        proxy_str = f"{ip}:{port}"
                        if is_valid_proxy(proxy_str):
                            proxy_type = "http"
                            if proxy_type_index is not None and len(columns) > proxy_type_index:
                                proxy_type = columns[proxy_type_index].text.strip().lower()
                                if "socks" in proxy_type:
                                    proxy_type = "socks5"
                                elif "https" in proxy_type: 
                                    proxy_type = "https"
                            proxy_str = f"{proxy_type}://{ip}:{port}"
                            proxies_list.append(proxy_str)
                            if show:
                                print(f"找到代理: {proxy_str}")
                        else:
                            if show_invalid:
                                logging.warning(f"无效的代理格式: {proxy_str}")
                    else:
                        if show_invalid:
                            logging.warning(f"无效的IP或端口: IP={ip}, Port={port}")
        
        if thread_monitor_enabled:
            with thread_stats_lock:
                thread_stats[threading.current_thread().name]['status'] = 'idle'
        return proxies_list
    except requests.exceptions.RequestException as e:
        logging.error(f"获取 {url} 失败: {e}")
        if thread_monitor_enabled:
            with thread_stats_lock:
                thread_stats[threading.current_thread().name]['status'] = 'error'
        return []

# 去重函数
def deduplicate_proxies(filename=None, debug=False, new_proxies=None):
    if filename is None:
        filename = "proxy_list.txt"
    if not os.path.exists(filename):
        logging.error(f"文件 {filename} 不存在。")
        return

    with open(filename, 'r') as f:
        existing_proxies = [line.strip() for line in f if line.strip()]
    
    if new_proxies:
        existing_proxies.extend(new_proxies)

    if debug:
        logging.info(f"去重前代理数量: {len(existing_proxies)}")
        logging.info(f"有效代理数量: {len([proxy for proxy in existing_proxies if is_valid_proxy(proxy)])}")

    unique_proxies = list(set(existing_proxies))
    if debug:
        logging.info(f"去重后代理数量: {len(unique_proxies)}")
        removed_proxies = set(existing_proxies) - set(unique_proxies)
        if removed_proxies:
            logging.info(f"被去除的代理: {removed_proxies}")

    with open(filename, 'w') as f:
        for proxy in unique_proxies:
            f.write(f"{proxy}\n")
    logging.info(f"去重后的代理已保存到 {filename}")

# 从 .txt 文件中读取网站列表
def read_proxy_sites_from_file(filename="proxy_sites.txt"):
    proxy_sites = []
    if not os.path.exists(filename):
        logging.error(f"文件 {filename} 不存在。")
        return proxy_sites

    with open(filename, 'r') as f:
        for line in f:
            url = line.strip()
            if url:
                proxy_sites.append({
                    'url': url,
                    'table_id': None,
                    'ip_index': 0,
                    'port_index': 1,
                    'proxy_type_index': None
                })
    return proxy_sites

# 删除前缀函数
def remove_prefix_from_file(filename="proxy_list.txt"):
    if not os.path.exists(filename):
        logging.error(f"文件 {filename} 不存在。")
        return

    with open(filename, 'r') as f:
        lines = f.readlines()

    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith(('http://', 'https://', 'socks5://')):
            line = line.split("://")[1]
        cleaned_lines.append(line + "\n")

    with open(filename, 'w') as f:
        f.writelines(cleaned_lines)

    logging.info(f"已删除 {filename} 中所有行的前缀。")

# 线程监控函数
def monitor_threads(interval=5):
    while True:
        with thread_stats_lock:
            active_threads = {k: v for k, v in thread_stats.items() 
                            if v.get('status') not in ['idle', 'error']}
            print("\n当前活跃线程状态:")
            for thread_name, info in active_threads.items():
                duration = time.time() - info.get('start_time', time.time())
                print(f"{thread_name}: {info.get('status', 'unknown')} - 运行时间: {duration:.2f}秒")
                if info.get('status') == 'crawling':
                    print(f"   正在爬取: {info.get('url')}")
                elif info.get('status') == 'validating':
                    print(f"   正在验证: {info.get('proxy')}")
        time.sleep(interval)

# 主函数
def main(proxy=None, validate=False, show=False, verify_url="http://httpbin.org/ip", verify_ssl=False, 
         no_prefix=False, add_prefix=False, timestamp=False, deduplicate=False, deduplicate_file=None, 
         deduplicate_after_save=False, show_invalid=False, simple_report=False, verbose=False, 
         overnight=False, interval=2, validate_timeout=10, request_timeout=10, deduplicate_debug=False, 
         remove_prefix=False, crawl_threads=5, validate_threads=10, monitor=False):
    
    global thread_monitor_enabled
    thread_monitor_enabled = monitor
    
    if monitor:
        monitor_thread = Thread(target=monitor_threads, daemon=True)
        monitor_thread.start()

    all_proxies = []
    task_queue = queue.Queue()

    # 如果需要去重
    if deduplicate:
        deduplicate_proxies(deduplicate_file, deduplicate_debug)
        return

    # 将任务放入队列
    for site in proxy_sites:
        task_queue.put(site)

    # 爬取线程函数
    def crawl_worker():
        while not task_queue.empty():
            try:
                site = task_queue.get()
                proxies = get_proxies_from_url(
                    site['url'], site['table_id'], site['ip_index'], 
                    site['port_index'], site['proxy_type_index'], 
                    proxy, show, show_invalid, verbose, interval, request_timeout
                )
                all_proxies.extend(proxies)
                if simple_report:
                    logging.info(f"从一个网站找到了 {len(proxies)} 个代理。")
                else:
                    logging.info(f"从 {site['url']} 找到了 {len(proxies)} 个代理。")
                task_queue.task_done()
            except Exception as e:
                logging.error(f"处理网站 {site['url']} 时出错: {e}")
                task_queue.task_done()

    # 创建并启动爬取线程
    for i in range(crawl_threads):
        t = Thread(target=crawl_worker, name=f"CrawlThread-{i}")
        t.start()

    # 等待所有爬取任务完成
    task_queue.join()

    unique_proxies = list(set(all_proxies))
    if simple_report:
        logging.info(f"\n总共找到了 {len(unique_proxies)} 个唯一代理。")
    else:
        logging.info(f"\n从所有网站总共找到了 {len(unique_proxies)} 个唯一代理。")

    # 验证代理IP
    if validate:
        valid_proxies = []
        successful_proxies_file = "successful_proxies.txt"
        validate_queue = queue.Queue()

        # 将验证任务放入队列
        for proxy in unique_proxies:
            validate_queue.put(proxy)

        # 验证线程函数
        def validate_worker():
            while not validate_queue.empty():
                try:
                    proxy = validate_queue.get()
                    result = validate_proxy(proxy, verify_url, validate_timeout, verify_ssl)
                    if result and result[2]:
                        valid_proxies.append(result[0])
                        with open(successful_proxies_file, 'a') as f:
                            f.write(f"{result[0]}\n")
                        logging.info(f"代理 {result[0]} 已追加到 {successful_proxies_file}")
                    validate_queue.task_done()
                except Exception as e:
                    logging.error(f"验证代理时出错: {e}")
                    validate_queue.task_done()

        # 创建并启动验证线程
        for i in range(validate_threads):
            t = Thread(target=validate_worker, name=f"ValidateThread-{i}")
            t.start()

        # 等待所有验证任务完成
        validate_queue.join()

        unique_proxies = valid_proxies
        logging.info(f"总共有效的代理: {len(unique_proxies)}")

    # 生成文件名
    if timestamp:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"proxy_list_{timestamp_str}.txt"
    else:
        filename = "proxy_list.txt"

    # 保存到文件
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            existing_proxies = set(f.read().splitlines())
    else:
        existing_proxies = set()

    with open(filename, 'a') as f:
        for proxy in unique_proxies:
            if proxy not in existing_proxies:
                if no_prefix:
                    if "://" in proxy:
                        proxy = proxy.split("://")[1]
                elif add_prefix:
                    if not proxy.startswith(('http://', 'https://', 'socks5://')):
                        proxy = f"http://{proxy}"
                f.write(f"{proxy}\n")
    logging.info(f"代理已保存到 {filename}")

    # 保存后去重
    if deduplicate_after_save:
        deduplicate_proxies(filename, deduplicate_debug, new_proxies=unique_proxies)

    # 删除前缀
    if remove_prefix:
        remove_prefix_from_file(filename)

    # 通宵挂机模式
    if overnight:
        logging.info("通宵挂机模式运行中...")
        time.sleep(interval)
        time.sleep(random.uniform(interval, interval + 2))
        logging.info("重新启动程序...")
        subprocess.run([sys.executable] + sys.argv)

if __name__ == "__main__":
    # 定义代理网站列表
    proxy_sites = read_proxy_sites_from_file("proxy_sites.txt")
    if not proxy_sites:
        # 如果没有读取到文件，使用默认网站列表
        proxy_sites = [
            {'url': 'https://www.free-proxy-list.net/', 'table_id': 'proxylisttable', 'ip_index': 0, 'port_index': 1, 'proxy_type_index': None},
            {'url': 'https://www.sslproxies.org/', 'table_id': 'proxylisttable', 'ip_index': 0, 'port_index': 1, 'proxy_type_index': None},
            {'url': 'https://www.us-proxy.org/', 'table_id': 'proxylisttable', 'ip_index': 0, 'port_index': 1, 'proxy_type_index': None},
        ]
        logging.warning("未找到proxy_sites.txt文件，使用默认代理网站列表")

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="从多个网站爬取代理服务器。", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--proxy', type=str, help="指定代理服务器（例如：http://127.0.0.1:8080 或 socks5://127.0.0.1:1080）。")
    parser.add_argument('--validate', action='store_true', help="在保存前验证代理IP是否可用。")
    parser.add_argument('--show', action='store_true', help="实时显示爬取到的代理IP。")
    parser.add_argument('--verify-url', type=str, default="http://httpbin.org/ip", help="指定用于验证代理的目标网站（默认：http://httpbin.org/ip）。")
    parser.add_argument('--verify-ssl', action='store_true', help="启用SSL验证（默认禁用）。")
    parser.add_argument('--no-prefix', action='store_true', help="保存代理IP时不添加前缀（默认不添加前缀）。")
    parser.add_argument('--add-prefix', action='store_true', help="保存代理IP时添加前缀（默认不添加前缀）。")
    parser.add_argument('--timestamp', action='store_true', help="保存代理IP时在文件名中添加时间戳（默认保存到 proxy_list.txt）。")
    parser.add_argument('--deduplicate', action='store_true', help="对文件中的代理IP进行去重。")
    parser.add_argument('--deduplicate-file', type=str, help="指定需要去重的文件（默认：proxy_list.txt）。")
    parser.add_argument('--deduplicate-after-save', action='store_true', help="保存代理IP后对文件内容进行去重。")
    parser.add_argument('--show-invalid', action='store_true', help="显示无效代理的警告信息。")
    parser.add_argument('--simple-report', action='store_true', help="显示简单的代理获取报告。")
    parser.add_argument('--verbose', action='store_true', help="显示详细的调试信息。")
    parser.add_argument('--overnight', action='store_true', help="启用通宵挂机无人值守模式。")
    parser.add_argument('--interval', type=int, default=2, help="自定义每次爬取的间隔时间（单位为秒，默认：2秒）。")
    parser.add_argument('--validate-timeout', type=int, default=30, help="验证代理IP的超时时间（单位为秒，默认：30秒）。")
    parser.add_argument('--request-timeout', type=int, default=30, help="发送请求的超时时间（单位为秒，默认：30秒）。")
    parser.add_argument('--deduplicate-debug', action='store_true', help="启用去重调试输出。")
    parser.add_argument('--remove-prefix', action='store_true', help="在程序完成后，删除 proxy_list.txt 中每一行的前缀（如 http://, https://, socks5://）。")
    parser.add_argument('--crawl-threads', type=int, default=5, help="指定爬取代理IP时的线程数（默认：5）。")
    parser.add_argument('--validate-threads', type=int, default=10, help="指定验证代理IP时的线程数（默认：10）。")
    parser.add_argument('--monitor', action='store_true', help="启用线程监控功能，实时显示线程状态。")
    
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )

    # 忽略SSL验证警告
    if not args.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 运行主函数
    main(
        args.proxy, args.validate, args.show, args.verify_url, args.verify_ssl,
        args.no_prefix, args.add_prefix, args.timestamp, args.deduplicate,
        args.deduplicate_file, args.deduplicate_after_save, args.show_invalid,
        args.simple_report, args.verbose, args.overnight, args.interval,
        args.validate_timeout, args.request_timeout, args.deduplicate_debug,
        args.remove_prefix, args.crawl_threads, args.validate_threads, args.monitor
    )
