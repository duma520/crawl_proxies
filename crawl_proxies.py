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

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 设置请求头，模拟浏览器访问
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 随机User-Agent列表
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
]

# 验证代理IP是否可用
def validate_proxy(proxy, verify_url, timeout=10, verify_ssl=False):
    try:
        proxies = {
            'http': proxy if proxy.startswith(('http://', 'https://', 'socks5://')) else f"http://{proxy}",
            'https': proxy if proxy.startswith(('http://', 'https://', 'socks5://')) else f"http://{proxy}"
        }
        start_time = time.time()
        response = requests.get(verify_url, proxies=proxies, timeout=timeout, verify=verify_ssl)
        end_time = time.time()
        if response.status_code == 200:
            latency = end_time - start_time
            logging.info(f"代理 {proxy} 有效。响应时间: {latency:.2f}秒")
            return proxy, latency, True  # 返回代理IP、延迟和可用性
        else:
            return proxy, None, False  # 返回代理IP、无延迟和不可用
    except Exception as e:
        logging.warning(f"代理 {proxy} 无效: {e}")
    return None, None, False

# 检查代理IP格式是否有效
def is_valid_proxy(proxy):
    # 正则表达式匹配IP:Port格式
    ip_port_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$')
    return bool(ip_port_pattern.match(proxy))

# 获取代理IP的函数
def get_proxies_from_url(url, table_id=None, ip_index=0, port_index=1, proxy_type_index=None, proxy=None, show=False, show_invalid=False, verbose=False, interval=2, request_timeout=30):
    try:
        proxies = None
        if proxy:
            if proxy.startswith('socks5'):
                proxies = {'http': proxy, 'https': proxy}
            else:
                proxies = {'http': proxy, 'https': proxy}

        # 如果需要身份验证
        auth = None
        if proxy and '@' in proxy:
            auth = proxy.split('@')[0]  # 提取用户名和密码
            proxy = proxy.split('@')[1]
            proxies = {
                'http': f"http://{auth}@{proxy}",
                'https': f"http://{auth}@{proxy}"
            }

        # 增加随机 User-Agent
        headers['User-Agent'] = random.choice(user_agents)

        # 增加请求间隔，避免被封禁
        time.sleep(interval)

        # 发送请求
        response = requests.get(url, headers=headers, proxies=proxies, timeout=request_timeout, verify=False)
        response.raise_for_status()

        # 打印响应内容（仅在启用 --verbose 时）
        if verbose:
            print(response.text)  # 调试时打开

        soup = BeautifulSoup(response.text, 'html.parser')

        proxies_list = []
        if table_id:
            table = soup.find('table', {'id': table_id})
        else:
            table = soup.find('table')

        if table:
            for row in table.find_all('tr')[1:]:
                columns = row.find_all('td')
                if len(columns) > max(ip_index, port_index):
                    ip = columns[ip_index].text.strip()
                    port = columns[port_index].text.strip()
                    # 清洗 IP 和端口数据
                    ip = re.sub(r'[^0-9.]', '', ip)  # 只保留数字和点
                    port = re.sub(r'[^0-9]', '', port)  # 只保留数字
                    if ip and port:  # 确保 IP 和端口不为空
                        proxy_str = f"{ip}:{port}"
                        # 检查代理IP格式是否有效
                        if is_valid_proxy(proxy_str):
                            proxy_type = "http"  # 默认类型为HTTP
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
        return proxies_list
    except requests.exceptions.RequestException as e:
        logging.error(f"获取 {url} 失败: {e}")
        return []

# 去重函数
def deduplicate_proxies(filename=None):
    if filename is None:
        filename = "proxy_list.txt"
    if not os.path.exists(filename):
        logging.error(f"文件 {filename} 不存在。")
        return

    with open(filename, 'r') as f:
        proxies = f.read().splitlines()

    unique_proxies = list(set(proxies))
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

# 定义要爬取的网站列表
proxy_sites = read_proxy_sites_from_file("proxy_sites.txt")

# 主函数
def main(proxy=None, validate=False, show=False, verify_url="https://www.google.com", verify_ssl=False, add_prefix=False, timestamp=False, deduplicate=False, deduplicate_file=None, deduplicate_after_save=False, show_invalid=False, simple_report=False, verbose=False, overnight=False, interval=2, validate_timeout=10, request_timeout=30):
    all_proxies = []

    # 如果需要去重
    if deduplicate:
        deduplicate_proxies(deduplicate_file)
        return

    # 多线程爬取代理IP
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for site in proxy_sites:
            future = executor.submit(get_proxies_from_url, site['url'], site['table_id'], site['ip_index'], site['port_index'], site['proxy_type_index'], proxy, show, show_invalid, verbose, interval, request_timeout)
            futures[future] = site['url']  # 记录 future 对应的网站 URL

        for future in as_completed(futures):
            proxies = future.result()
            all_proxies.extend(proxies)
            if simple_report:
                logging.info(f"从一个网站找到了 {len(proxies)} 个代理。")
            else:
                site_url = futures[future]
                logging.info(f"从 {site_url} 找到了 {len(proxies)} 个代理。")

    # 去重
    unique_proxies = list(set(all_proxies))
    if simple_report:
        logging.info(f"\n总共找到了 {len(unique_proxies)} 个唯一代理。")
    else:
        logging.info(f"\n从所有网站总共找到了 {len(unique_proxies)} 个唯一代理。")

    # 验证代理IP
    if validate:
        valid_proxies = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_proxy, proxy, verify_url, validate_timeout, verify_ssl) for proxy in unique_proxies]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    valid_proxies.append(result)
        unique_proxies = valid_proxies
        logging.info(f"总共有效的代理: {len(unique_proxies)}")

    # 生成文件名
    if timestamp:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"proxy_list_{timestamp_str}.txt"
    else:
        filename = "proxy_list.txt"

    # 保存到文件
    with open(filename, 'w') as f:
        for proxy in unique_proxies:
            if not add_prefix:
                # 去掉前缀
                proxy = proxy.split("://")[1]
            f.write(f"{proxy}\n")
    logging.info(f"代理已保存到 {filename}")

    # 保存后去重
    if deduplicate_after_save:
        deduplicate_proxies(filename)

    # 通宵挂机模式
    if overnight:
        logging.info("通宵挂机模式运行中...")
        time.sleep(interval)
        logging.info("重新启动程序...")
        subprocess.run([sys.executable] + sys.argv)

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="从多个网站爬取代理服务器。", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--proxy', type=str, help="指定代理服务器（例如：http://127.0.0.1:8080 或 socks5://127.0.0.1:1080）。")
    parser.add_argument('--validate', action='store_true', help="在保存前验证代理IP是否可用。")
    parser.add_argument('--show', action='store_true', help="实时显示爬取到的代理IP。")
    parser.add_argument('--verify-url', type=str, default="https://www.google.com", help="指定用于验证代理的目标网站（默认：https://www.google.com）。")
    parser.add_argument('--verify-ssl', action='store_true', help="启用SSL验证（默认禁用）。")
    parser.add_argument('--add-prefix', action='store_true', help="保存代理IP时添加前缀（http://、https:// 或 socks5://）。")
    parser.add_argument('--timestamp', action='store_true', help="保存代理IP时在文件名中添加时间戳（默认保存到 proxy_list.txt）。")
    parser.add_argument('--deduplicate', action='store_true', help="对文件中的代理IP进行去重。")
    parser.add_argument('--deduplicate-file', type=str, help="指定需要去重的文件（默认：proxy_list.txt）。")
    parser.add_argument('--deduplicate-after-save', action='store_true', help="保存代理IP后对文件内容进行去重。")
    parser.add_argument('--show-invalid', action='store_true', help="显示无效代理的警告信息。")
    parser.add_argument('--simple-report', action='store_true', help="显示简单的代理获取报告。")
    parser.add_argument('--verbose', action='store_true', help="显示详细的调试信息。")
    parser.add_argument('--overnight', action='store_true', help="启用通宵挂机无人值守模式。")
    parser.add_argument('--interval', type=int, default=2, help="自定义每次爬取的间隔时间（单位为秒，默认：2秒）。")
    parser.add_argument('--validate-timeout', type=int, default=10, help="验证代理IP的超时时间（单位为秒，默认：10秒）。")
    parser.add_argument('--request-timeout', type=int, default=30, help="发送请求的超时时间（单位为秒，默认：30秒）。")
    args = parser.parse_args()

    # 忽略SSL验证警告
    if not args.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 运行主函数
    main(args.proxy, args.validate, args.show, args.verify_url, args.verify_ssl, args.add_prefix, args.timestamp, args.deduplicate, args.deduplicate_file, args.deduplicate_after_save, args.show_invalid, args.simple_report, args.verbose, args.overnight, args.interval, args.validate_timeout, args.request_timeout)
