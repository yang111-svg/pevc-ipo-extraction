# 招股说明书下载方法

## 方法一：手动下载（推荐第一周使用）

### 巨潮资讯网下载步骤

1. **访问网站**: 打开 https://www.cninfo.com.cn
2. **搜索公司**: 在搜索框输入 "股票代码 公司简称 招股说明书"
   - 例如: "001282 三联锻造 招股说明书"
3. **筛选文件类型**: 在搜索结果中选择 "招股说明书" 类型
4. **确认版本**: 查看公告日期和文件标题，确认是目标文件
5. **下载PDF**: 点击PDF链接下载
6. **文件命名**: 按照 `股票代码_公司简称_文件类型.pdf` 格式命名
   - 例如: `001282_三联锻造_IPO招股说明书.pdf`

### 北京证券交易所下载步骤

1. **访问网站**: 打开 https://www.bse.cn
2. **进入信息披露**: 点击导航栏 "信息披露"
3. **搜索公司**: 输入股票代码或公司简称
   - 例如: "920100" 或 "三协电机"
4. **筛选文件**: 在文件类型中选择 "招股说明书"
5. **下载PDF**: 点击PDF链接下载
6. **文件命名**: 按照 `股票代码_公司简称_文件类型.pdf` 格式命名

## 方法二：Python脚本下载（推荐后续使用）

### 基础下载脚本

```python
import requests
import os

# 创建下载目录
os.makedirs('downloads', exist_ok=True)

# 定义下载列表
download_list = [
    {
        'stock_code': '001282',
        'company_name': '三联锻造',
        'url': 'https://static.cninfo.com.cn/finalpage/2023-05-17/1216830304.PDF'
    },
    # 添加更多...
]

# 下载函数
def download_pdf(url, filename):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"✓ 下载成功: {filename}")
            return True
        else:
            print(f"✗ 下载失败: {filename}, 状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 下载错误: {filename}, 错误: {str(e)}")
        return False

# 批量下载
for item in download_list:
    filename = f"downloads/{item['stock_code']}_{item['company_name']}_IPO招股说明书.pdf"
    download_pdf(item['url'], filename)
```

## 下载日志记录

每次下载后，需要记录到 `logs/download_log.csv`：

```csv
company_name,stock_code,prospectus_url,file_name,download_time,status,file_size,error_message
三联锻造,001282,https://static.cninfo.com.cn/...,001282_三联锻造_IPO招股说明书.pdf,2025-06-01,success,10240000,
```

## 常见问题

### 1. 下载失败
- **原因**: 网络问题、链接失效、需要验证码
- **解决**: 尝试手动下载，或更换网络环境

### 2. 文件损坏
- **原因**: 下载不完整
- **解决**: 重新下载，检查文件大小是否正常

### 3. 找不到文件
- **原因**: 搜索关键词不准确
- **解决**: 尝试使用股票代码搜索，或到交易所官网查找

## 文件保存规范

1. **目录结构**: 所有PDF保存在 `downloads/` 目录
2. **命名规则**: `股票代码_公司简称_文件类型.pdf`
3. **版本管理**: 如果同一公司有多个版本，添加版本号
   - 例如: `001282_三联锻造_IPO招股说明书_注册稿.pdf`
