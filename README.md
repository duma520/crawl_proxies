# 全方位代理爬取工具使用说明书

## 一、工具概述

本工具是一个功能强大的代理IP爬取、验证和管理系统，能够从多个公开代理网站自动收集代理IP，并进行有效性验证和去重处理。适用于网络安全研究人员、数据分析师、爬虫开发者等需要大量代理IP的用户群体。

## 二、适用人群

1. **技术人员**：开发人员、网络安全工程师、数据分析师
2. **企业用户**：需要大规模网络数据采集的企业
3. **个人用户**：需要匿名浏览或绕过地理限制的个人
4. **研究人员**：进行网络行为研究的学术人员

## 三、核心功能

### 1. 代理爬取功能
- 支持从多个预设代理网站自动爬取代理IP
- 可自定义爬取目标网站列表
- 多线程并发爬取提高效率

### 2. 代理验证功能
- 实时验证代理IP的有效性
- 支持HTTP/HTTPS/SOCKS5协议验证
- 可自定义验证目标网站

### 3. 代理管理功能
- 自动去重处理
- 支持多种格式保存
- 可按需添加或删除协议前缀

## 四、详细使用指南

### 1. 基础使用

**安装依赖：**
```
pip install requests beautifulsoup4 fake-useragent fake-headers
```

**基本运行：**
```
python crawl_proxies.py
```

### 2. 参数详解

#### 爬取控制参数
- `--proxy`：指定代理服务器进行爬取
- `--crawl-threads`：设置爬取线程数(默认5)
- `--interval`：设置爬取间隔时间(秒)

#### 验证参数
- `--validate`：启用代理验证
- `--validate-threads`：设置验证线程数(默认10)
- `--verify-url`：设置验证目标URL
- `--validate-timeout`：设置验证超时时间(秒)

#### 输出控制
- `--show`：实时显示爬取结果
- `--no-prefix`：保存无协议前缀的代理
- `--add-prefix`：自动添加协议前缀
- `--timestamp`：在文件名中添加时间戳

#### 高级功能
- `--overnight`：启用无人值守模式
- `--monitor`：启用线程监控
- `--deduplicate`：执行去重操作
- `--remove-prefix`：移除已有前缀

### 3. 配置文件

创建`proxy_sites.txt`文件可自定义爬取源，每行一个URL，格式示例：
```
https://www.free-proxy-list.net/
https://www.sslproxies.org/
```

### 4. 典型使用场景

#### 场景一：快速获取有效代理
```
python crawl_proxies.py --validate --validate-threads 20
```

#### 场景二：大规模代理采集(夜间模式)
```
python crawl_proxies.py --overnight --interval 5 --crawl-threads 10
```

#### 场景三：代理列表维护
```
python crawl_proxies.py --deduplicate --deduplicate-file proxies.txt
```

## 五、技术原理

1. **爬取机制**：使用BeautifulSoup解析HTML表格，提取代理IP和端口
2. **验证机制**：通过请求目标网站测试代理可达性
3. **并发模型**：采用线程池实现高效并发处理
4. **防检测**：随机User-Agent和请求头模拟浏览器行为

## 六、注意事项

1. 请遵守目标网站的robots.txt协议
2. 高频访问可能导致IP被封禁
3. 免费代理质量参差不齐，建议二次验证
4. 长期运行建议使用`--interval`设置合理间隔

## 七、常见问题解答

**Q：为什么有些代理验证失败？**
A：免费代理通常稳定性较差，失效快是正常现象

**Q：如何提高爬取速度？**
A：增加`--crawl-threads`参数值，但需注意不要过度请求

**Q：验证URL可以更改吗？**
A：可以，通过`--verify-url`参数指定任何可达的URL

## 八、版本更新说明

- **Version 40**：新增线程监控功能，优化验证逻辑
- **Version 39**：增加SOCKS5协议支持
- **Version 38**：改进去重算法，提升性能

## 九、技术支持

如需进一步技术支持，请联系开发者或提交issue到项目仓库。本工具持续更新，建议定期检查新版本获取最新功能。
