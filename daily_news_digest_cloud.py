#!/usr/bin/env python3
"""Fetch serious RSS/Atom headlines and generate a balanced morning news digest for iPhone Shortcuts / Obsidian.

Steven's rules:
- 10 finance / markets items: roughly 5 China + 5 international.
- 10 technology / AI items: roughly 5 China + 5 international.
- 10 private equity / investment market items: roughly 5 China + 5 international.
- Prefer serious/professional sources; filter gossip, PR fluff, routine bank/insurance promo, and low-value gadget posts.
- Keep source language; summaries use RSS descriptions/snippets.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = REPO_ROOT / "output"
OUTPUT_DAILY_DIR = OUTPUT_DIR / "daily"
TIMEZONE = dt.datetime.now().astimezone().tzinfo

CATEGORIES = [
    {"key": "finance", "title": "财经 / 金融", "limit": 10, "cn_target": 4, "intl_target": 4},
    {"key": "tech_ai", "title": "科技 / AI", "limit": 10, "cn_target": 4, "intl_target": 4},
    {"key": "pe", "title": "私募股权 / 投资市场", "limit": 10, "cn_target": 4, "intl_target": 4},
]

# region: cn / intl. Google News feeds are fallback/search feeds; item source is extracted when available.
FEEDS = [
    # 财经 / 金融 — international
    {"name": "NYTimes Business", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "lang": "en", "region": "intl", "category": "finance", "weight": 8},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "lang": "en", "region": "intl", "category": "finance", "weight": 9},
    {"name": "CNBC Finance", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "lang": "en", "region": "intl", "category": "finance", "weight": 7},
    {"name": "Google News Global Finance", "url": "https://news.google.com/rss/search?q=(Reuters%20OR%20Bloomberg%20OR%20Financial%20Times%20OR%20WSJ)%20(finance%20OR%20markets%20OR%20economy%20OR%20IPO%20OR%20M%26A)%20when:3d&hl=en-US&gl=US&ceid=US:en", "lang": "en", "region": "intl", "category": "finance", "weight": 6},

    # 财经 / 金融 — China
    {"name": "Google News China Finance", "url": "https://news.google.com/rss/search?q=(%E8%B4%A2%E6%96%B0%20OR%20%E7%AC%AC%E4%B8%80%E8%B4%A2%E7%BB%8F%20OR%20%E7%BB%8F%E6%B5%8E%E8%A7%82%E5%AF%9F%E6%8A%A5%20OR%20%E8%AF%81%E5%88%B8%E6%97%B6%E6%8A%A5%20OR%20%E4%B8%8A%E8%AF%81%E6%8A%A5)%20(%E8%B4%A2%E7%BB%8F%20OR%20%E9%87%91%E8%9E%8D%20OR%20%E8%B5%84%E6%9C%AC%E5%B8%82%E5%9C%BA%20OR%20A%E8%82%A1%20OR%20%E6%B8%AF%E8%82%A1%20OR%20IPO)%20when:3d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "finance", "weight": 7},
    {"name": "Google News China Macro", "url": "https://news.google.com/rss/search?q=(%E4%B8%AD%E5%9B%BD%20OR%20%E5%A4%AE%E8%A1%8C%20OR%20%E8%AF%81%E7%9B%91%E4%BC%9A%20OR%20%E8%B4%A2%E6%94%BF%E9%83%A8)%20(%E5%AE%8F%E8%A7%82%20OR%20%E5%88%A9%E7%8E%87%20OR%20%E6%B1%87%E7%8E%87%20OR%20%E8%B5%84%E6%9C%AC%E5%B8%82%E5%9C%BA%20OR%20%E5%80%BA%E5%88%B8)%20when:3d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "finance", "weight": 6},

    # 科技 / AI — international
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "lang": "en", "region": "intl", "category": "tech_ai", "weight": 9},
    {"name": "NYTimes Technology", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "lang": "en", "region": "intl", "category": "tech_ai", "weight": 8},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lang": "en", "region": "intl", "category": "tech_ai", "weight": 7},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "lang": "en", "region": "intl", "category": "tech_ai", "weight": 7},
    {"name": "Google News Global AI", "url": "https://news.google.com/rss/search?q=(AI%20OR%20artificial%20intelligence%20OR%20semiconductor%20OR%20chips%20OR%20data%20center)%20(Reuters%20OR%20Bloomberg%20OR%20Financial%20Times%20OR%20MIT%20Technology%20Review%20OR%20Wired)%20when:3d&hl=en-US&gl=US&ceid=US:en", "lang": "en", "region": "intl", "category": "tech_ai", "weight": 6},

    # 科技 / AI — China. 36氪 is kept only with strict filters; IT之家 removed.
    {"name": "36氪", "url": "https://36kr.com/feed", "lang": "zh", "region": "cn", "category": "tech_ai", "weight": 5},
    {"name": "Google News China AI", "url": "https://news.google.com/rss/search?q=(%E6%9C%BA%E5%99%A8%E4%B9%8B%E5%BF%83%20OR%20%E9%87%8F%E5%AD%90%E4%BD%8D%20OR%20%E8%B4%A2%E6%96%B0%20OR%2036%E6%B0%AA)%20(AI%20OR%20%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD%20OR%20%E5%A4%A7%E6%A8%A1%E5%9E%8B%20OR%20%E8%8A%AF%E7%89%87%20OR%20%E7%AE%97%E5%8A%9B%20OR%20%E6%95%B0%E6%8D%AE%E4%B8%AD%E5%BF%83)%20when:3d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "tech_ai", "weight": 7},
    {"name": "Google News China Tech Finance", "url": "https://news.google.com/rss/search?q=(%E4%B8%AD%E5%9B%BD%20OR%20%E5%9B%BD%E5%86%85)%20(%E7%A7%91%E6%8A%80%20OR%20%E5%8D%8A%E5%AF%BC%E4%BD%93%20OR%20%E8%8A%AF%E7%89%87%20OR%20AI)%20(%E6%8A%95%E8%B5%84%20OR%20%E8%9E%8D%E8%B5%84%20OR%20IPO%20OR%20%E5%B9%B6%E8%B4%AD%20OR%20%E7%9B%91%E7%AE%A1)%20when:5d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "tech_ai", "weight": 6},

    # 私募股权 / 投资市场 — international
    {"name": "PE Hub", "url": "https://www.pehub.com/feed/", "lang": "en", "region": "intl", "category": "pe", "weight": 8},
    {"name": "Private Equity International", "url": "https://www.privateequityinternational.com/feed/", "lang": "en", "region": "intl", "category": "pe", "weight": 9},
    {"name": "Buyouts", "url": "https://www.buyoutsinsider.com/feed/", "lang": "en", "region": "intl", "category": "pe", "weight": 8},
    {"name": "AltAssets", "url": "https://www.altassets.net/feed", "lang": "en", "region": "intl", "category": "pe", "weight": 7},
    {"name": "Google News Global PE", "url": "https://news.google.com/rss/search?q=(private%20equity%20OR%20buyout%20OR%20secondaries%20OR%20LPs%20OR%20GPs%20OR%20fundraising)%20(Reuters%20OR%20Bloomberg%20OR%20Financial%20Times%20OR%20WSJ%20OR%20PitchBook%20OR%20Preqin)%20when:5d&hl=en-US&gl=US&ceid=US:en", "lang": "en", "region": "intl", "category": "pe", "weight": 6},

    # 私募股权 / 投资市场 — China
    {"name": "Google News China PE Fundraising", "url": "https://news.google.com/rss/search?q=(%E6%8A%95%E4%B8%AD%E7%BD%91%20OR%20%E6%B8%85%E7%A7%91%20OR%2036%E6%B0%AA%20OR%20%E8%B4%A2%E6%96%B0%20OR%20%E7%AC%AC%E4%B8%80%E8%B4%A2%E7%BB%8F%20OR%20%E8%AF%81%E5%88%B8%E6%97%B6%E6%8A%A5)%20(%E4%B8%AD%E5%9B%BD%20OR%20%E5%9B%BD%E5%86%85%20OR%20%E4%BA%BA%E6%B0%91%E5%B8%81%20OR%20%E5%88%9B%E6%8A%95)%20(%E5%AE%8C%E6%88%90%E5%8B%9F%E8%B5%84%20OR%20%E9%A6%96%E5%85%B3%20OR%20%E6%9C%80%E7%BB%88%E5%85%B3%E9%97%AD%20OR%20%E6%96%B0%E5%9F%BA%E9%87%91%20OR%20%E6%AF%8D%E5%9F%BA%E9%87%91%20OR%20S%E5%9F%BA%E9%87%91%20OR%20%E4%BA%BA%E6%B0%91%E5%B8%81%E5%9F%BA%E9%87%91)%20when:30d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "pe", "weight": 8},
    {"name": "Google News China PE Deals", "url": "https://news.google.com/rss/search?q=(%E6%8A%95%E4%B8%AD%E7%BD%91%20OR%20%E6%B8%85%E7%A7%91%20OR%2036%E6%B0%AA%20OR%20%E8%B4%A2%E6%96%B0%20OR%20%E7%AC%AC%E4%B8%80%E8%B4%A2%E7%BB%8F%20OR%20%E8%AF%81%E5%88%B8%E6%97%B6%E6%8A%A5)%20(%E4%B8%AD%E5%9B%BD%20OR%20%E5%9B%BD%E5%86%85%20OR%20%E4%BA%BA%E6%B0%91%E5%B8%81%20OR%20%E5%88%9B%E4%B8%9A%E5%85%AC%E5%8F%B8)%20(%E5%AE%8C%E6%88%90%E8%9E%8D%E8%B5%84%20OR%20%E8%8E%B7%E6%8A%95%20OR%20%E9%A2%86%E6%8A%95%20OR%20%E6%88%98%E7%95%A5%E8%9E%8D%E8%B5%84%20OR%20A%E8%BD%AE%20OR%20B%E8%BD%AE%20OR%20C%E8%BD%AE%20OR%20%E8%BF%87%E4%BA%BF%E5%85%83)%20when:21d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "pe", "weight": 8},
    {"name": "Google News China PE Exits", "url": "https://news.google.com/rss/search?q=(%E6%8A%95%E4%B8%AD%E7%BD%91%20OR%20%E6%B8%85%E7%A7%91%20OR%2036%E6%B0%AA%20OR%20%E8%B4%A2%E6%96%B0%20OR%20%E7%AC%AC%E4%B8%80%E8%B4%A2%E7%BB%8F%20OR%20%E8%AF%81%E5%88%B8%E6%97%B6%E6%8A%A5)%20(%E4%B8%AD%E5%9B%BD%20OR%20%E5%9B%BD%E5%86%85%20OR%20A%E8%82%A1%20OR%20%E6%B8%AF%E8%82%A1%20OR%20%E4%BA%BA%E6%B0%91%E5%B8%81)%20(IPO%20OR%20%E4%B8%8A%E5%B8%82%20OR%20%E9%80%80%E5%87%BA%20OR%20%E5%B9%B6%E8%B4%AD%20OR%20%E6%94%B6%E8%B4%AD%20OR%20%E8%82%A1%E6%9D%83%E8%BD%AC%E8%AE%A9%20OR%20%E8%80%81%E8%82%A1%E8%BD%AC%E8%AE%A9)%20when:30d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "pe", "weight": 8},
    {"name": "Google News China Startup Funding", "url": "https://news.google.com/rss/search?q=%E5%AE%8C%E6%88%90%E8%9E%8D%E8%B5%84%20%E9%A2%86%E6%8A%95%20%E8%BF%87%E4%BA%BF%E5%85%83%20when:30d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "pe", "weight": 7},
    {"name": "Google News China Fundraising Simple", "url": "https://news.google.com/rss/search?q=%E5%AE%8C%E6%88%90%E5%8B%9F%E8%B5%84%20%E6%96%B0%E5%9F%BA%E9%87%91%20%E5%88%9B%E6%8A%95%20when:30d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "pe", "weight": 7},
    {"name": "Google News China Exit Simple", "url": "https://news.google.com/rss/search?q=%E5%B9%B6%E8%B4%AD%20%E9%80%80%E5%87%BA%20%E8%82%A1%E6%9D%83%E8%BD%AC%E8%AE%A9%20IPO%20when:30d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", "lang": "zh", "region": "cn", "category": "pe", "weight": 7},
]

MARKER_START = "<!-- daily-news-digest:start -->"
MARKER_END = "<!-- daily-news-digest:end -->"
USER_AGENT = "Mozilla/5.0 (compatible; ObsidianDailyNews/1.2; +https://obsidian.md)"

LOW_VALUE_GLOBAL = [
    "浮生别院", "偶像", "明星", "综艺", "八卦", "电影", "定档", "海报", "演唱会", "票房", "汪汪队",
    "耳机", "手机壳", "保护壳", "配色", "机模", "真无线", "开售", "促销", "优惠券", "降价",
    "签约车手", "张雪机车", "携手合作", "亮相", "荣获", "助力", "赋能", "发布会", "品牌活动",
    "中信银行", "国寿", "中国人寿", "寿险", "信用卡权益", "客户服务节",
    "手机新浪", "AIBase", "24h|", "24h｜", "8点1氪", "早报", "午报", "晚报", "一图读懂",
    "官方网站", "信息披露平台", "嘉宾详情", "峰会—嘉宾", "SuperLink", "超级链接", "启幕",
    "白皮书", "创投生态", "生态", "高质量发展", "万亿公司", "论坛", "峰会", "大会", "圆桌",
    "如何投资", "新周期", "周期性现象", "观点", "专访", "今年IPO爆发",
    "足球", "soccer", "drug designer", "医生版", "船舶", "推进系统", "技工", "培训", "prediction markets",
    "信用卡", "credit card", "ai girlfriend", "girlfriend", "steroid olympics",
    "The Download:", "Echo Hub", "customizable new look", "board of directors",
    "Jimmy Kimmel", "Brendan Carr", "broadcasting company", "social media",
]

TECH_AI_MUST_HAVE = [
    "AI", "人工智能", "大模型", "模型", "机器人", "具身智能", "自动驾驶",
    "半导体", "芯片", "算力", "数据中心", "GPU", "Nvidia", "英伟达",
    "OpenAI", "Anthropic", "DeepSeek", "云基础设施", "云计算", "量子",
    "semiconductor", "chip", "chips", "robot", "robotics", "autonomous",
    "data center", "datacenter", "GPU", "LLM", "large language model", "artificial intelligence",
]

GOOGLE_ALLOWED_SOURCES = {
    "finance": ["Reuters", "Bloomberg", "Financial Times", "Wall Street Journal", "WSJ", "CNBC", "纽约时报", "财新", "第一财经", "经济观察报", "证券时报", "上证报"],
    "tech_ai": ["Reuters", "Bloomberg", "Financial Times", "MIT Technology Review", "Wired", "The Verge", "TechCrunch", "纽约时报", "财新", "第一财经", "证券时报", "机器之心", "量子位", "36氪"],
    "pe": ["Reuters", "Bloomberg", "Financial Times", "Wall Street Journal", "WSJ", "PitchBook", "Preqin", "Private Equity International", "PE Hub", "Buyouts", "投中网", "清科", "财新", "第一财经", "证券时报", "投资界", "36氪", "亿欧", "动脉网", "创业邦"],
}

GOOGLE_BLOCKED_SOURCES = ["手机新浪网", "新浪财经", "AIBase", "marketscreener.com", "Investing.com", "The Economic Times", "亚洲日报"]

# Do not remove these entirely: they are high-signal but often paywalled. Penalize and label them.
PAYWALL_SOURCES = ["Bloomberg", "Financial Times", "FT", "Wall Street Journal", "WSJ", "NYTimes", "New York Times", "纽约时报", "财新周刊"]

CATEGORY_HIGH_VALUE = {
    "finance": [
        "央行", "证监会", "财政部", "利率", "汇率", "通胀", "CPI", "PPI", "GDP", "债券", "资本市场",
        "A股", "港股", "IPO", "并购", "重组", "监管", "房地产", "银行业", "券商", "基金", "宏观",
        "Fed", "rates", "inflation", "market", "markets", "economy", "stocks", "bonds", "IPO", "M&A", "tariff",
    ],
    "tech_ai": [
        "AI", "人工智能", "大模型", "模型", "芯片", "半导体", "算力", "数据中心", "云", "机器人", "自动驾驶",
        "监管", "融资", "IPO", "并购", "OpenAI", "Nvidia", "semiconductor", "chips", "data center", "cloud",
    ],
    "pe": [
        "完成募资", "首关", "最终关闭", "新基金", "人民币基金", "母基金", "S基金", "二级市场", "LP", "GP",
        "完成融资", "获投", "领投", "跟投", "战略融资", "A轮", "B轮", "C轮", "D轮", "过亿元", "数亿元",
        "IPO", "上市", "退出", "并购", "收购", "股权转让", "老股转让", "控股权",
        "buyout", "private equity", "fundraising", "secondaries", "exit", "acquire", "acquisition", "portfolio", "CalPERS", "pension", "valuation",
    ],
}

SOURCE_BONUS = {
    "Reuters": 5, "Bloomberg": 5, "Financial Times": 5, "Wall Street Journal": 5, "WSJ": 5,
    "财新": 5, "第一财经": 4, "经济观察报": 4, "证券时报": 4, "上证报": 4,
    "MIT Technology Review": 5, "Nature": 5, "Science": 5, "Wired": 4,
    "Private Equity International": 5, "PE Hub": 4, "Buyouts": 4, "PitchBook": 5, "Preqin": 5,
    "投中网": 5, "清科": 5, "母基金周刊": 4,
}


def clean_text(value: Optional[str], max_len: int = 280) -> str:
    if not value:
        return ""
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > max_len:
        value = value[: max_len - 1].rstrip() + "…"
    return value


def parse_date(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(TIMEZONE)
    except Exception:
        pass
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(TIMEZONE)
    except Exception:
        return None


def child_text(el: ET.Element, names: Iterable[str]) -> Optional[str]:
    suffixes = tuple(name.split("}")[-1] for name in names)
    for child in el:
        tag = child.tag.split("}")[-1]
        if tag in suffixes and child.text:
            return child.text
    return None


def child_attr(el: ET.Element, name: str, attr: str) -> Optional[str]:
    for child in el:
        if child.tag.split("}")[-1] == name:
            return child.attrib.get(attr)
    return None


def fetch_feed(feed: Dict[str, object], timeout: int = 20) -> List[Dict[str, object]]:
    req = urllib.request.Request(str(feed["url"]), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    results: List[Dict[str, object]] = []

    for item in root.findall(".//item"):
        title = clean_text(child_text(item, ["title"]), 180)
        link = clean_text(child_text(item, ["link"]), 500)
        desc = clean_text(child_text(item, ["description", "summary", "encoded"]), 240)
        published = parse_date(child_text(item, ["pubDate", "date", "published", "updated"]))
        source = clean_text(child_text(item, ["source"]), 80)
        display_name = source if str(feed.get("name", "")).startswith("Google News") and source else str(feed["name"])
        if title and link:
            results.append({**feed, "name": display_name, "feed_name": feed["name"], "title": title, "link": link, "summary": desc, "published": published})

    for entry in [e for e in root.iter() if e.tag.split("}")[-1] == "entry"]:
        title = clean_text(child_text(entry, ["title"]), 180)
        link = ""
        for child in entry:
            if child.tag.split("}")[-1] == "link":
                rel = child.attrib.get("rel", "alternate")
                if rel == "alternate" and child.attrib.get("href"):
                    link = clean_text(child.attrib.get("href"), 500)
                    break
        desc = clean_text(child_text(entry, ["summary", "content"]), 240)
        published = parse_date(child_text(entry, ["published", "updated"]))
        if title and link:
            results.append({**feed, "name": str(feed["name"]), "feed_name": feed["name"], "title": title, "link": link, "summary": desc, "published": published})

    return results


def is_recent(item: Dict[str, object], now: dt.datetime, hours: int) -> bool:
    published = item.get("published")
    if not isinstance(published, dt.datetime):
        return True
    return now - dt.timedelta(hours=hours) <= published <= now + dt.timedelta(hours=2)


def text_blob(item: Dict[str, object]) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')} {item.get('name', '')}"


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    low = text.lower()
    return any(k.lower() in low for k in keywords)


def is_tech_ai_relevant(text: str) -> bool:
    low = text.lower()
    strict_patterns = [
        r"\bai\b",
        r"artificial intelligence",
        r"machine learning",
        r"deep learning",
        r"\bllm\b",
        r"large language model",
        r"openai", r"anthropic", r"deepmind", r"deepseek",
        r"nvidia", r"gpu", r"semiconductor", r"\bchip(s)?\b",
        r"data center", r"datacenter",
        r"robot", r"robotics", r"autonomous",
        r"人工智能", r"大模型", r"具身智能", r"机器人", r"自动驾驶",
        r"半导体", r"芯片", r"算力", r"数据中心", r"英伟达", r"云基础设施",
    ]
    return any(re.search(pattern, low, flags=re.I) for pattern in strict_patterns)


def quality_score(item: Dict[str, object]) -> int:
    category = str(item.get("category", ""))
    blob = text_blob(item)
    source = str(item.get("name", ""))
    feed_name = str(item.get("feed_name", ""))
    if contains_any(blob, LOW_VALUE_GLOBAL) or contains_any(source, GOOGLE_BLOCKED_SOURCES):
        return -999
    if category == "tech_ai":
        tech_block = [
            "信用卡", "credit card", "ai girlfriend", "girlfriend", "steroid olympics",
            "spacex", "rocket", "satellite", "the download:", "echo hub", "ring’s ai",
            "customizable new look", "board of directors", "leave microsoft’s board",
            "jimmy kimmel", "brendan carr", "broadcasting company", "social media",
        ]
        if contains_any(blob, tech_block) or not is_tech_ai_relevant(blob):
            return -999

    if category == "pe" and item.get("region") == "cn":
        must_have = [
            "完成募资", "首关", "最终关闭", "新基金", "人民币基金", "母基金", "S基金", "二级市场",
            "完成融资", "获投", "领投", "跟投", "战略融资", "A轮", "B轮", "C轮", "D轮", "过亿元", "数亿元",
            "IPO", "上市", "退出", "并购", "收购", "股权转让", "老股转让", "控股权",
        ]
        pe_cn_block = ["美国", "欧洲", "中东"]
        if contains_any(blob, pe_cn_block):
            return -999
        if not contains_any(blob, must_have):
            return -999
    if feed_name.startswith("Google News"):
        allowed = GOOGLE_ALLOWED_SOURCES.get(category, [])
        if allowed and not contains_any(source, allowed):
            return -999
    score = int(item.get("weight", 0))
    if contains_any(source, PAYWALL_SOURCES):
        score -= 2
    score += sum(2 for k in CATEGORY_HIGH_VALUE.get(category, []) if k.lower() in blob.lower())
    score += sum(v for k, v in SOURCE_BONUS.items() if k.lower() in blob.lower())
    if len(str(item.get("summary", ""))) >= 80:
        score += 1
    if str(item.get("feed_name", "")).startswith("Google News"):
        score -= 1  # useful fallback, but prefer direct serious feeds when comparable
    return score


def sort_key(item: Dict[str, object]) -> Tuple[int, dt.datetime]:
    published = item.get("published")
    when = published if isinstance(published, dt.datetime) else dt.datetime.min.replace(tzinfo=TIMEZONE)
    return (int(item.get("score", 0)), when)


def dedupe(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    output = []
    for item in items:
        title_norm = re.sub(r"\s+[-|].*$", "", str(item.get("title", ""))).strip().lower()
        key = title_norm or str(item.get("link", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def balanced_region_pick(items: List[Dict[str, object]], limit: int, cn_target: int, intl_target: int, per_source_cap: int = 2) -> List[Dict[str, object]]:
    items = sorted(items, key=sort_key, reverse=True)
    selected: List[Dict[str, object]] = []

    def add_from(region: str, target: int) -> None:
        counts: Dict[str, int] = {}
        for item in items:
            if len([x for x in selected if x.get("region") == region]) >= target:
                break
            if item in selected or item.get("region") != region:
                continue
            source = str(item.get("name", ""))
            if counts.get(source, 0) >= per_source_cap:
                continue
            selected.append(item)
            counts[source] = counts.get(source, 0) + 1

    add_from("cn", cn_target)
    add_from("intl", intl_target)

    # Fill any shortfall with best remaining, still limiting source concentration.
    while len(selected) < limit:
        added = False
        for item in items:
            if item in selected:
                continue
            source = str(item.get("name", ""))
            if len([x for x in selected if x.get("name") == source]) >= per_source_cap:
                continue
            selected.append(item)
            added = True
            break
        if not added:
            break

    return sorted(selected[:limit], key=sort_key, reverse=True)


def collect_items(now: dt.datetime, recent_hours: int, per_feed_limit: int) -> tuple[Dict[str, List[Dict[str, object]]], List[str]]:
    grouped: Dict[str, List[Dict[str, object]]] = {cat["key"]: [] for cat in CATEGORIES}
    failures: List[str] = []

    for feed in FEEDS:
        try:
            items = fetch_feed(feed)
            items = [item for item in items if is_recent(item, now, recent_hours)]
            for item in items:
                item["score"] = quality_score(item)
            items = [item for item in items if int(item.get("score", 0)) > 0]
            items.sort(key=sort_key, reverse=True)
            grouped[str(feed["category"])].extend(items[:per_feed_limit])
        except Exception as exc:
            failures.append(f"{feed['name']} ({exc.__class__.__name__})")

    for cat in CATEGORIES:
        key = cat["key"]
        grouped[key] = balanced_region_pick(
            dedupe(grouped[key]),
            limit=int(cat["limit"]),
            cn_target=int(cat["cn_target"]),
            intl_target=int(cat["intl_target"]),
            per_source_cap=2,
        )
    return grouped, failures


def format_digest(grouped: Dict[str, List[Dict[str, object]]], failures: List[str], now: dt.datetime) -> str:
    total = sum(len(grouped.get(cat["key"], [])) for cat in CATEGORIES)
    lines = [MARKER_START, "## 今日新闻", ""]
    lines.append("> [!info] 阅读说明")
    lines.append("> 已按严肃媒体/专业来源、主题相关度、信息密度过滤；国内/国际尽量均衡但不机械凑数。")
    lines.append("> 摘要来自 RSS/新闻源描述，保留原文语言；`可能需订阅` 表示该来源可能有付费墙。")
    lines.append("")

    if total == 0:
        lines += ["> [!warning] 今天暂时没有抓取到新闻。", ""]

    callout_type = {
        "finance": "quote",
        "tech_ai": "example",
        "pe": "tip",
    }

    for cat in CATEGORIES:
        items = grouped.get(cat["key"], [])
        cn_count = len([i for i in items if i.get("region") == "cn"])
        intl_count = len([i for i in items if i.get("region") == "intl"])
        ctype = callout_type.get(cat["key"], "note")
        lines.append(f"> [!{ctype}] {cat['title']}")
        lines.append(f"> {len(items)}/{cat['limit']} · 国内 {cn_count} / 国际 {intl_count}")
        lines.append(">")
        if not items:
            lines.append("> 暂无。")
        for idx, item in enumerate(items, start=1):
            published = item.get("published")
            time_text = published.strftime('%H:%M') if isinstance(published, dt.datetime) else ""
            source_name = str(item.get('name', ''))
            region_text = "国内" if item.get("region") == "cn" else "国际"
            paywall_text = " · `可能需订阅`" if contains_any(source_name, PAYWALL_SOURCES) else ""
            meta_parts = [source_name, region_text]
            if time_text:
                meta_parts.append(time_text)
            meta = " · ".join([part for part in meta_parts if part]) + paywall_text
            summary = str(item.get("summary", "")).strip()
            lines.append(f"> **{idx}. [{item['title']}]({item['link']})**")
            lines.append(f"> <small>{meta}</small>")
            if summary:
                lines.append(f"> {summary}")
            lines.append(">")
        lines.append("")

    if failures:
        lines += ["> [!warning] 抓取失败但不影响成稿的来源", "> " + "、".join(failures), ""]
    lines += ["#daily-news", MARKER_END, ""]
    return "\n".join(lines)


def frontmatter_for_news(day: dt.date, now: dt.datetime) -> str:
    return "\n".join([
        "---",
        "type: daily-news",
        f"date: {day.isoformat()}",
        "generated: true",
        f"generated_at: {now.isoformat(timespec='seconds')}",
        "categories:",
        "  - finance",
        "  - tech-ai",
        "  - private-equity",
        "tags:",
        "  - daily-news",
        "---",
        "",
    ])


def daily_note_section(digest: str) -> str:
    """Content to insert directly into the Obsidian Daily Note."""
    return digest.strip() + "\n"


def news_note_content(day: dt.date, now: dt.datetime, digest: str) -> str:
    return frontmatter_for_news(day, now) + digest.strip() + "\n"


def write_outputs(day: dt.date, now: dt.datetime, digest: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DAILY_DIR.mkdir(parents=True, exist_ok=True)

    section = daily_note_section(digest)
    news = news_note_content(day, now, digest)

    # Stable URLs for iPhone Shortcuts.
    (OUTPUT_DIR / "latest-daily-section.md").write_text(section, encoding="utf-8")
    (OUTPUT_DIR / "latest-news.md").write_text(news, encoding="utf-8")
    (OUTPUT_DIR / "latest-date.txt").write_text(day.isoformat() + "\n", encoding="utf-8")

    # Dated archive copy inside this cloud repo.
    (OUTPUT_DAILY_DIR / f"{day.isoformat()} News.md").write_text(news, encoding="utf-8")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD; defaults to today in runner timezone")
    parser.add_argument("--recent-hours", type=int, default=336, help="Freshness window; PE and serious CN sources may update less frequently")
    parser.add_argument("--per-feed-limit", type=int, default=12, help="Max quality-filtered items from each source before balancing")
    args = parser.parse_args(argv)

    now = dt.datetime.now().astimezone()
    day = dt.date.fromisoformat(args.date) if args.date else now.date()

    grouped, failures = collect_items(now, args.recent_hours, args.per_feed_limit)
    digest = format_digest(grouped, failures, now)
    write_outputs(day, now, digest)

    counts = ", ".join(
        f"{cat['title']}={len(grouped.get(cat['key'], []))}" for cat in CATEGORIES
    )
    print(f"Wrote {counts} to output/latest-daily-section.md, output/latest-news.md, and output/daily/{day.isoformat()} News.md")
    if failures:
        print("Failures:", "; ".join(failures), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
