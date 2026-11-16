from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from xml.etree import ElementTree as ET
import html
import json
import os
import re
import time as clock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TZ = timezone(timedelta(hours=8), "Asia/Taipei")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TaiwanStockInfo/1.0)",
    "Accept": "application/json,application/rss+xml,application/xml,text/xml,*/*",
}
INDUSTRIES = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業",
    "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "14": "建材營造",
    "15": "航運業", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "19": "綜合", "20": "其他", "21": "化學工業", "22": "生技醫療",
    "23": "油電燃氣", "24": "半導體業", "25": "電腦及週邊設備", "26": "光電業",
    "27": "通信網路業", "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
    "31": "其他電子業", "32": "文化創意業", "33": "農業科技業", "35": "綠能環保業",
}
FEEDS = [
    ("Yahoo 國際財經", "https://tw.stock.yahoo.com/rss/url/d/e/N12.html", "yahoo"),
    ("鉅亨網頭條", "https://news.google.com/rss/search?q=site%3Anews.cnyes.com%2Fnews%2Fid+%28%E5%9C%8B%E9%9A%9B+OR+%E6%94%BF%E7%B6%93+OR+%E6%94%BF%E7%AD%96+OR+%E7%B6%93%E6%BF%9F%29&hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant", "cnyes"),
    ("Reuters Business", "https://news.google.com/rss/search?q=site%3Areuters.com%2Fbusiness+%28politics+OR+economy+OR+trade+OR+policy+OR+energy%29&hl=en-US&gl=US&ceid=US%3Aen", "reuters"),
]
INCLUDE = (
    "政策", "關稅", "貿易", "制裁", "央行", "利率", "通膨", "經濟", "政府", "選舉", "外交",
    "戰爭", "能源", "石油", "天然氣", "供應鏈", "出口管制", "AI", "晶片", "半導體", "美中",
    "中國", "美國", "日本", "歐洲", "聯準會", "Fed", "Trump", "China", "Iran", "Israel",
    "Nvidia", "產業", "企業", "財政", "GDP", "就業", "regulation", "tariff", "trade", "sanction",
    "central bank", "inflation", "government", "election", "diplomacy", "war", "energy", "oil",
    "supply chain", "export control", "chip", "semiconductor", "United States", "Europe", "policy", "economy",
)
EXCLUDE = (
    "開盤", "收盤", "漲幅", "跌幅", "上漲", "下跌", "大漲", "大跌", "指數", "股市走勢", "盤中",
    "台股", "股價", "行情", "報價", "shares rise", "shares fall", "stocks rise", "stocks fall",
    "stocks climb", "stocks drop", "stock market", "equities jump", "equities slide",
)
TOPIC_TERMS = (
    "關稅", "貿易", "制裁", "央行", "利率", "通膨", "政策", "政府", "外交", "能源", "油價",
    "供應鏈", "半導體", "AI", "中國", "美國", "Fed", "Trump", "Nvidia", "tariff", "trade",
    "energy", "policy", "economy", "Reuters",
)


def fetch(url, timeout=20):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def write_json(name, payload):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))


def field(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def load_companies():
    endpoints = (
        ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "listed"),
        ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "otc"),
    )
    items = []
    for url, market in endpoints:
        rows = json.loads(fetch(url))
        for row in rows:
            code = field(row, "公司代號", "SecuritiesCompanyCode", "公司代碼")
            name = field(row, "公司簡稱", "CompanyAbbreviation", "公司名稱", "CompanyName")
            industry = field(row, "產業別", "SecuritiesIndustryCode", "Industry", "IndustryName")
            if code and name:
                items.append({
                    "code": code,
                    "name": name,
                    "sector": INDUSTRIES.get(industry, industry or "未分類"),
                    "market": market,
                    "open": None,
                    "previousClose": None,
                })
    return items


def parse_price(value):
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def update_quotes(items):
    # TWSE MIS exposes today's open as `o` and the prior close as `y`.
    today = datetime.now(TZ).strftime("%Y%m%d")
    for offset in range(0, len(items), 65):
        group = items[offset:offset + 65]
        channels = [
            f"{'otc' if stock['market'] == 'otc' else 'tse'}_{stock['code']}.tw"
            for stock in group
        ]
        query = urlencode({
            "ex_ch": "|".join(channels),
            "json": "1",
            "delay": "0",
            "_": str(int(clock.time() * 1000)),
        }, safe="|_.,")
        try:
            result = json.loads(fetch("https://mis.twse.com.tw/stock/api/getStockInfo.jsp?" + query))
            by_code = {str(row.get("c", "")): row for row in result.get("msgArray", [])}
            for stock in group:
                row = by_code.get(stock["code"])
                if row:
                    stock["name"] = row.get("n") or stock["name"]
                    row_date = re.sub(r"\D", "", row.get("d", ""))
                    stock["open"] = parse_price(row.get("o")) if row_date == today else None
                    stock["previousClose"] = parse_price(row.get("y"))
        except Exception as exc:
            print(f"Quote batch {offset // 65 + 1} failed: {exc}", flush=True)
        clock.sleep(0.12)


def news_window(now):
    previous = now.date() - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return (
        datetime.combine(previous, time(13, 30), TZ),
        datetime.combine(now.date(), time(9, 0), TZ),
    )


def parse_date(value):
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TZ)
        return parsed.astimezone(TZ)
    except Exception:
        return None


def update_news(now):
    start, end = news_window(now)
    candidates = []
    for source, url, kind in FEEDS:
        try:
            root = ET.fromstring(fetch(url))
            for entry in root.findall(".//item"):
                title = html.unescape((entry.findtext("title") or "").strip())
                link = (entry.findtext("link") or "").strip()
                published = parse_date(entry.findtext("pubDate") or "")
                source_node = entry.find("source")
                publisher = (source_node.text or "") if source_node is not None else ""
                description = re.sub(r"<[^>]+>", " ", entry.findtext("description") or "")
                description = html.unescape(re.sub(r"\s+", " ", description)).strip()
                combined = (title + " " + description + " " + publisher).lower()
                if not title or not link or not published or not start <= published < end:
                    continue
                if any(word.lower() in combined for word in EXCLUDE):
                    continue
                if not any(word.lower() in combined for word in INCLUDE):
                    continue
                all_text = link + " " + title + " " + description + " " + publisher
                if kind == "cnyes" and "cnyes" not in all_text.lower() and "鉅亨" not in all_text:
                    continue
                if kind == "reuters" and "reuters" not in all_text.lower():
                    continue
                candidates.append({
                    "title": title,
                    "url": link,
                    "source": source,
                    "published": published.isoformat(),
                    "summary": description[:240],
                })
        except Exception as exc:
            print(f"News feed failed ({source}): {exc}", flush=True)

    for item in candidates:
        text = (item["title"] + " " + item["summary"]).lower()
        item["_topics"] = {term.lower() for term in TOPIC_TERMS if term.lower() in text}
        item["_score"] = len(item["_topics"])
    candidates.sort(key=lambda item: (item["_score"], item["published"]), reverse=True)
    selected, topic_counts = [], {}
    for item in candidates:
        if len(selected) == 5:
            break
        if sum(topic_counts.get(term, 0) > 0 for term in item["_topics"]) >= 2:
            continue
        for term in item["_topics"]:
            topic_counts[term] = topic_counts.get(term, 0) + 1
        item.pop("_topics", None)
        item.pop("_score", None)
        selected.append(item)
    return {
        "updatedAt": now.isoformat(),
        "windowStart": start.isoformat(),
        "windowEnd": end.isoformat(),
        "items": selected,
    }


def main():
    os.makedirs(DATA, exist_ok=True)
    print("Loading TWSE/TPEx company directory...", flush=True)
    stocks = load_companies()
    if not stocks:
        raise RuntimeError("The exchange directory returned no stocks.")
    print(f"Loaded {len(stocks)} stocks; collecting open and previous close...", flush=True)
    update_quotes(stocks)
    if not any(stock["open"] is not None or stock["previousClose"] is not None for stock in stocks):
        raise RuntimeError("TWSE MIS returned no quote data.")
    write_json("stocks.json", {"updatedAt": datetime.now(TZ).isoformat(), "items": stocks})
    print("Collecting the filtered news window...", flush=True)
    news = update_news(datetime.now(TZ))
    write_json("news.json", news)
    print(f"Wrote {len(stocks)} stock records and {len(news['items'])} news stories.", flush=True)


if __name__ == "__main__":
    main()
