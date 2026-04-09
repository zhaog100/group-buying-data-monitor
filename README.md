# 团购+外卖实时自动数据监测系统

基于 OpenClaw Skills 的多平台数据抓取、分析与飞书分发系统。

## 🎯 功能

### 评价平台（10:00-20:00，每2小时更新）
- **大众点评**：评论数、评分、内容、门店排名
- **抖音来客**：评论数、用户级别、评分、消费人数
- **高德地图**：评论数、评分、回头率、榜单

### 外卖平台（午餐10:30-12:30 / 晚餐17:00-19:00，每30分钟更新）
- **美团/饿了么/京东**：订单量、转化率、商圈排名、门店评分

### 通知
- 飞书 Webhook / App 消息卡片推送
- 告警（评分下降、排名下降、抓取失败）

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 为 `.env`，填入门店信息和飞书配置：

```bash
cp .env.example .env
```

### 3. 运行

```bash
# 单次运行
python main.py

# 按调度规则持续运行
python main.py --scheduled

# 只抓取评价平台
python main.py --review-only

# 只抓取外卖平台
python main.py --delivery-only

# 不推送飞书
python main.py --no-notify
```

## ⚙️ 配置说明

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `STORE_NAME` | 门店名称 | 我的餐厅 |
| `STORE_CITY` | 城市 | 北京 |
| `STORE_DISTRICT` | 区域 | 朝阳区 |
| `DIANPING_SHOP_ID` | 大众点评门店ID | H1234567 |
| `DOUYIN_SHOP_ID` | 抖音来客门店ID | 7123456789 |
| `GAODE_POI_ID` | 高德地图POI ID | B12345678 |
| `MEITUAN_SHOP_ID` | 美团外卖门店ID | 12345678 |
| `ELEME_SHOP_ID` | 饿了么门店ID | 12345678 |
| `JD_SHOP_ID` | 京东到家门店ID | 12345678 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL | https://open.feishu.cn/... |
| `FEISHU_APP_ID` | 飞书 App ID | cli_xxx |
| `FEISHU_APP_SECRET` | 飞书 App Secret | xxx |
| `PROXY_ENABLED` | 启用代理 | true |
| `HTTPS_PROXY` | HTTPS代理地址 | http://proxy:8080 |

## 📁 项目结构

```
├── main.py                 # 主入口
├── src/
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── models.py           # 数据模型
│   ├── scraper_base.py     # 抓取器基类（反爬+重试）
│   ├── scraper_review.py   # 评价平台抓取器
│   ├── scraper_delivery.py # 外卖平台抓取器
│   ├── scheduler.py        # 调度器
│   └── feishu.py           # 飞书推送
├── tests/
│   └── test_monitor.py     # 单元测试
├── reports/                # 报告输出目录
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 反爬策略

- UA 随机轮换
- 请求间隔随机延迟（1-3秒）
- 自动重试（最多3次，指数退避）
- 代理池支持
- 浏览器指纹模拟

## 📊 数据准确率

目标：**98%+**

实现方式：
- 多数据源交叉验证
- 异常值自动检测和告警
- 抓取失败自动重试
- 数据质量评分

## 📄 License

MIT
