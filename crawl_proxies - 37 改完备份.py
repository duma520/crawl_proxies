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

# 初始化 UserAgent 和 Headers 对象
ua = UserAgent()
headers_faker = Headers(
    browser="chrome",  # 可以指定浏览器类型，如 "chrome", "firefox", "safari" 等
    os="win",  # 可以指定操作系统，如 "win", "mac", "linux" 等
    headers=True  # 生成完整的请求头
)

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
    # 正则表达式匹配 IP:Port 或 协议://IP:Port 格式
    proxy_pattern = re.compile(r'^(http://|https://|socks5://)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$')
    match = proxy_pattern.match(proxy)
    if not match:
        return False

    # 提取 IP 和端口
    ip = match.group(2)
    port = match.group(3)

    # 检查 IP 和端口是否有效
    return is_valid_ip(ip) and is_valid_port(port)

# 检查 IP 地址是否有效
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

# 检查端口号是否有效
def is_valid_port(port):
    try:
        port_num = int(port)
        if 1 <= port_num <= 65535:
            return True
    except ValueError:
        pass
    return False

# 验证代理IP是否可用
def validate_proxy(proxy, verify_url, timeout=30, verify_ssl=False):
    # 检查代理格式是否有效
    if not is_valid_proxy(proxy):
        logging.warning(f"代理 {proxy} 格式无效。")
        return None, None, False

    prefixes = ['http://', 'https://', 'socks5://']
    for prefix in prefixes:
        try:
            # 强制尝试所有前缀，即使代理字符串已经包含前缀
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
    return None, None, False

# 获取代理IP的函数
def get_proxies_from_url(url, table_id=None, ip_index=0, port_index=1, proxy_type_index=None, proxy=None, show=False, show_invalid=False, verbose=False, interval=2, request_timeout=30):
    time.sleep(random.uniform(interval, interval + 2))  # 随机增加0到2秒的间隔
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

        # 增加随机 User-Agent 和请求头
        headers = get_random_headers()

        # 增加请求间隔，避免被封禁
        time.sleep(interval)
        time.sleep(random.uniform(interval, interval + 2))  # 随机增加0到2秒的间隔

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
def deduplicate_proxies(filename=None, debug=False, new_proxies=None):
    if filename is None:
        filename = "proxy_list.txt"
    if not os.path.exists(filename):
        logging.error(f"文件 {filename} 不存在。")
        return

    # 读取文件中的现有代理
    with open(filename, 'r') as f:
        existing_proxies = [line.strip() for line in f if line.strip()]  # 去除空行和多余的空格
    
    # 如果有新代理，合并到现有代理中
    if new_proxies:
        existing_proxies.extend(new_proxies)

    if debug:
        logging.info(f"去重前代理数量: {len(existing_proxies)}")
        logging.info(f"有效代理数量: {len([proxy for proxy in existing_proxies if is_valid_proxy(proxy)])}")

    # 去重
    unique_proxies = list(set(existing_proxies))
    if debug:
        logging.info(f"去重后代理数量: {len(unique_proxies)}")
        removed_proxies = set(existing_proxies) - set(unique_proxies)
        if removed_proxies:
            logging.info(f"被去除的代理: {removed_proxies}")

    # 保存去重后的代理
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

# 删除前缀函数
def remove_prefix_from_file(filename="proxy_list.txt"):
    if not os.path.exists(filename):
        logging.error(f"文件 {filename} 不存在。")
        return

    with open(filename, 'r') as f:
        lines = f.readlines()

    # 删除前缀
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith(('http://', 'https://', 'socks5://')):
            line = line.split("://")[1]
        cleaned_lines.append(line + "\n")

    # 写回文件
    with open(filename, 'w') as f:
        f.writelines(cleaned_lines)

    logging.info(f"已删除 {filename} 中所有行的前缀。")

# 主函数
def main(proxy=None, validate=False, show=False, verify_url="http://httpbin.org/ip", verify_ssl=False, no_prefix=False, add_prefix=False, timestamp=False, deduplicate=False, deduplicate_file=None, deduplicate_after_save=False, show_invalid=False, simple_report=False, verbose=False, overnight=False, interval=2, validate_timeout=30, request_timeout=30, deduplicate_debug=False, remove_prefix=False):
    all_proxies = []

    # 如果需要去重
    if deduplicate:
        deduplicate_proxies(deduplicate_file, deduplicate_debug)
        return

    # 多线程爬取代理IP
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for site in proxy_sites:
            try:
                future = executor.submit(get_proxies_from_url, site['url'], site['table_id'], site['ip_index'], site['port_index'], site['proxy_type_index'], proxy, show, show_invalid, verbose, interval, request_timeout)
                time.sleep(random.uniform(interval, interval + 2))  # 随机增加0到2秒的间隔
                futures[future] = site['url']  # 记录 future 对应的网站 URL
            except Exception as e:
                logging.error(f"网站 {site['url']} 访问失败: {e}")
                continue

        for future in as_completed(futures):
            try:
                proxies = future.result()
                all_proxies.extend(proxies)
                if simple_report:
                    logging.info(f"从一个网站找到了 {len(proxies)} 个代理。")
                else:
                    site_url = futures[future]
                    logging.info(f"从 {site_url} 找到了 {len(proxies)} 个代理。")
            except Exception as e:
                logging.error(f"处理网站 {futures[future]} 时出错: {e}")

    # 去重
    unique_proxies = list(set(all_proxies))
    if simple_report:
        logging.info(f"\n总共找到了 {len(unique_proxies)} 个唯一代理。")
    else:
        logging.info(f"\n从所有网站总共找到了 {len(unique_proxies)} 个唯一代理。")

    # 验证代理IP
    if validate:
        valid_proxies = []
        successful_proxies_file = "successful_proxies.txt"  # 定义文件名

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_proxy, proxy, verify_url, validate_timeout, verify_ssl) for proxy in unique_proxies]
            for future in as_completed(futures):
                result = future.result()
                if result and result[2]:  # 如果代理有效
                    valid_proxies.append(result[0])  # 提取代理字符串
                    # 追加到 successful_proxies.txt
                    with open(successful_proxies_file, 'a') as f:
                        f.write(f"{result[0]}\n")
                    logging.info(f"代理 {result[0]} 已追加到 {successful_proxies_file}")

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

    with open(filename, 'a') as f:  # 使用追加模式
        for proxy in unique_proxies:
            if proxy not in existing_proxies:  # 检查是否已经存在
                if no_prefix:
                    # 去掉前缀
                    if "://" in proxy:
                        proxy = proxy.split("://")[1]
                elif add_prefix:
                    # 添加前缀
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
        time.sleep(random.uniform(interval, interval + 2))  # 随机增加0到2秒的间隔
        logging.info("重新启动程序...")
        subprocess.run([sys.executable] + sys.argv)

if __name__ == "__main__":
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
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,  # 默认显示 INFO 及以上级别的日志
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler()  # 输出到控制台
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
        args.remove_prefix
    )
