import os
import re
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from playwright.sync_api import sync_playwright

Base = declarative_base()

class bus_route_orm(Base):
    __tablename__ = "data_route_list"
    route_id = Column(String, primary_key=True)
    route_name = Column(String)

class bus_stop_orm(Base):
    __tablename__ = "data_route_info_busstop"
    stop_id = Column(Integer)
    arrival_info = Column(String)
    stop_number = Column(Integer, primary_key=True)
    stop_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    direction = Column(String, primary_key=True)
    route_id = Column(String, primary_key=True)

class taipei_route_info:
    """
    管理特定公車路線和方向的站點資料抓取、解析和儲存。
    """
    def __init__(self, route_id: str, direction: str):
        self.route_id = route_id
        self.direction = direction  # 'go' (去程) 或 'come' (回程)
        self.url = f'https://ebus.gov.taipei/Route/StopsOfRoute?routeid={route_id}'
        self.content = None

    def fetch_route_info(self):
        """
        使用 Playwright 抓取特定路線的站點頁面 HTML 內容。
        """
        print(f"正在抓取路線 {self.route_id} ({'去程' if self.direction == 'go' else '回程'}) 的站點資料...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url)

            # 如果是回程，點擊回程按鈕
            if self.direction == 'come':
                try:
                    page.click('a.stationlist-come-go-gray.stationlist-come', timeout=5000)
                    page.wait_for_timeout(1000)  # 給予時間讓頁面內容更新
                except Exception as e:
                    print(f"❌ 點擊回程按鈕失敗或未找到按鈕: {e}")
            
            page.wait_for_timeout(3000)  # 等待頁面載入和渲染
            self.content = page.content()
            browser.close()

    def parse_route_info(self) -> pd.DataFrame:
        """
        從抓取的 HTML 內容中解析公車站點的詳細資訊。
        """
        pattern = re.compile(
            r'<li>.*?<span class="auto-list-stationlist-position.*?">(.*?)</span>\s*'
            r'<span class="auto-list-stationlist-number">\s*(\d+)</span>\s*'
            r'<span class="auto-list-stationlist-place">(.*?)</span>.*?'
            r'<input[^>]+name="item\.UniStopId"[^>]+value="(\d+)"[^>]*>.*?'
            r'<input[^>]+name="item\.Latitude"[^>]+value="([\d\.]+)"[^>]*>.*?'
            r'<input[^>]+name="item\.Longitude"[^>]+value="([\d\.]+)"[^>]*>',
            re.DOTALL
        )
        matches = pattern.findall(self.content)

        if not matches:
            print(f"❌ 路線 {self.route_id} ({'去程' if self.direction == 'go' else '回程'}) 未找到站點資料。")
            return pd.DataFrame()

        self.dataframe = pd.DataFrame(
            matches,
            columns=["arrival_info", "stop_number", "stop_name", "stop_id", "latitude", "longitude"]
        )
        self.dataframe["direction"] = self.direction
        self.dataframe["route_id"] = self.route_id
        
        self.dataframe["latitude"] = self.dataframe["latitude"].astype(float)
        self.dataframe["longitude"] = self.dataframe["longitude"].astype(float)
        
        print(f"✅ 路線 {self.route_id} ({'去程' if self.direction == 'go' else '回程'}) 成功解析 {len(self.dataframe)} 個站點。")
        return self.dataframe

def get_route_id_by_name(route_name: str, session) -> str:
    """
    根據公車路線名稱查詢路線 ID。
    """
    result = session.query(bus_route_orm).filter(bus_route_orm.route_name == route_name).first()
    if result:
        return result.route_id
    return None

def interactive_interface():
    """
    提供互動介面，讓使用者輸入公車路線名稱，查詢到站資訊。
    """
    # 初始化資料庫連線
    engine = create_engine('sqlite:///data/taipei_bus.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    route_name = input("請輸入公車路線名稱：").strip()
    direction = input("請選擇方向 ('go' 表示去程, 'come' 表示回程)：").strip()

    if direction not in ['go', 'come']:
        print("❌ 輸入的方向無效，請重新執行程式。")
        return

    route_id = get_route_id_by_name(route_name, session)
    if not route_id:
        print(f"❌ 找不到名稱為「{route_name}」的公車路線。")
        return

    try:
        route_info = taipei_route_info(route_id, direction)
        route_info.fetch_route_info()
        df = route_info.parse_route_info()

        if df.empty:
            print("❌ 未找到任何到站資訊。")
        else:
            print("\n以下是該路線的到站資訊：")
            print(df[["stop_number", "stop_name", "arrival_info"]])
    except Exception as e:
        print(f"❌ 查詢過程中發生錯誤：{e}")

if __name__ == "__main__":
    interactive_interface()