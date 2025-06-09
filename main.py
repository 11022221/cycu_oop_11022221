# -*- coding: utf-8 -*-
import os
import re
import pandas as pd
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, declarative_base
from playwright.sync_api import sync_playwright

# 建立資料夾與資料庫連線
WORKING_DIR = "data"
os.makedirs(WORKING_DIR, exist_ok=True)
DB_PATH = f"{WORKING_DIR}/hermes_ebus_taipei.sqlite3"
engine = create_engine(f"sqlite:///{DB_PATH}")
Base = declarative_base()

# ORM: 公車列表
class RouteList(Base):
    __tablename__ = "data_route_list"
    route_id = Column(String, primary_key=True)
    route_name = Column(String)

# ORM: 即時站牌資訊
class RealtimeInfo(Base):
    __tablename__ = "data_realtime_info"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String)
    direction = Column(String)
    stop_number = Column(Integer)
    stop_name = Column(String)
    arrival_info = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def fetch_all_routes():
    """爬取所有公車路線並儲存至資料庫"""
    url = "https://ebus.gov.taipei/ebus?ct=all"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # 滾動多次以確保所有路線載入
        for _ in range(5):  # 滾動多次
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)  # 每次等待 1 秒

        content = page.content()
        browser.close()

    # 更新正則表達式以匹配所有路線
    pattern = r"<li><a href=\"javascript:go\('(.*?)'\)\">(.*?)</a></li>"
    matches = re.findall(pattern, content)
    if not matches:
        raise ValueError("❌ 無法解析公車路線")
    
    print(f"匹配到的公車路線數量：{len(matches)}")  # 確認抓到的路線數量
    for route_id, route_name in matches:
        # 檢查是否已存在該 route_id
        existing_route = session.query(RouteList).filter_by(route_id=route_id).first()
        if not existing_route:
            session.add(RouteList(route_id=route_id, route_name=route_name.strip()))
    session.commit()
    print(f"✅ 已儲存 {len(matches)} 筆公車路線資料")

def fetch_realtime_info(route_id: str, direction: str) -> pd.DataFrame:
    """根據 route_id 與方向（go/come）爬取即時站牌資訊"""
    url = f"https://ebus.gov.taipei/Route/StopsOfRoute?routeid={route_id}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        if direction == "come":
            page.click('a.stationlist-come-go-gray.stationlist-come')
        page.wait_for_timeout(5000)  # 等待 5 秒
        content = page.content()
        browser.close()

    pattern = re.compile(
        r'<li>.*?<span class="auto-list-stationlist-position.*?">(.*?)</span>\s*'
        r'<span class="auto-list-stationlist-number">\s*(\d+)</span>\s*'
        r'<span class="auto-list-stationlist-place">(.*?)</span>',
        re.DOTALL
    )
    matches = pattern.findall(content)
    if not matches:
        raise ValueError("❌ 找不到即時資料")

    df = pd.DataFrame(matches, columns=["arrival_info", "stop_number", "stop_name"])
    df["stop_number"] = df["stop_number"].astype(int)
    df["direction"] = direction
    df["route_id"] = route_id
    return df

def save_realtime_info(df: pd.DataFrame):
    """儲存即時資訊到資料庫"""
    for _, row in df.iterrows():
        session.add(RealtimeInfo(
            route_id=row["route_id"],
            direction=row["direction"],
            stop_number=row["stop_number"],
            stop_name=row["stop_name"],
            arrival_info=row["arrival_info"]
        ))
    session.commit()

def find_route_and_time(start_stop: str, end_stop: str):
    """根據起始站和目標站查詢公車路線及到站時間"""
    routes = session.query(RealtimeInfo).filter(
        RealtimeInfo.stop_name.in_([start_stop, end_stop])
    ).all()

    if not routes:
        print(f"❌ 找不到包含「{start_stop}」和「{end_stop}」的公車路線")
        return

    route_times = {}
    for route in routes:
        if route.stop_name == start_stop:
            route_times.setdefault(route.route_id, {})["start_time"] = route.arrival_info
        elif route.stop_name == end_stop:
            route_times.setdefault(route.route_id, {})["end_time"] = route.arrival_info

    for route_id, times in route_times.items():
        start_time = times.get("start_time", "未知")
        end_time = times.get("end_time", "未知")
        print(f"🚍 公車路線代碼：{route_id}")
        print(f"起始站到站時間：{start_time} 分鐘")
        print(f"終點站到站時間：{end_time} 分鐘")

def check_route_list():
    """檢查資料庫中的公車路線"""
    routes = session.query(RouteList).all()
    print(f"資料庫中的公車路線數量：{len(routes)}")
    for route in routes:
        print(f"路線 ID: {route.route_id}, 路線名稱: {route.route_name}")

def check_realtime_info():
    """檢查資料庫中的即時站牌資訊"""
    stops = session.query(RealtimeInfo).all()
    print(f"資料庫中的即時站牌資訊數量：{len(stops)}")
    for stop in stops:
        print(f"路線 ID: {stop.route_id}, 方向: {stop.direction}, 站牌編號: {stop.stop_number}, 站牌名稱: {stop.stop_name}, 到站時間: {stop.arrival_info}")

def main():
    # 使用者輸入
    start_stop = input("請輸入起始站名稱：").strip()
    end_stop = input("請輸入終點站名稱：").strip()

    # 查詢公車路線及到站時間
    find_route_and_time(start_stop, end_stop)

if __name__ == "__main__":
    main()
