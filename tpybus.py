# -*- coding: utf-8 -*-
import sys
import io
import os
import re
import pandas as pd
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from sqlalchemy import Column, String, Float, Integer

# 設定標準輸出編碼為 UTF-8，以避免中文字符亂碼問題
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

Base = declarative_base()

class bus_route_orm(Base):
    __tablename__ = 'data_route_list'
    route_id = Column(String, primary_key=True)
    route_name = Column(String)
    route_data_updated = Column(Integer, default=0)

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

class taipei_route_list:
    """
    管理台北市公車所有路線的抓取、解析和儲存。
    """
    def __init__(self, working_directory='data'):
        self.working_directory = working_directory
        # 確保工作目錄存在
        os.makedirs(self.working_directory, exist_ok=True)
        self.url = 'https://ebus.gov.taipei/ebus?ct=all'
        self.content = None
        # 抓取所有路線列表頁的 HTML 內容
        self._fetch_content()

        # 建立 SQLite 資料庫引擎
        self.engine = create_engine(f'sqlite:///{self.working_directory}/hermes_ebus_taipei.sqlite3')
        # 連接資料庫並創建表格（如果不存在）
        self.engine.connect()
        Base.metadata.create_all(self.engine)
        # 創建資料庫會話
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def _fetch_content(self):
        """
        使用 Playwright 抓取所有路線列表頁的 HTML 內容。
        """
        print(f"正在抓取所有路線列表頁面: {self.url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) # 無頭模式運行
            page = browser.new_page()
            page.goto(self.url)
            page.wait_for_timeout(3000) # 等待頁面載入和渲染
            self.content = page.content()
            browser.close()
        
        # 將抓取到的 HTML 內容儲存到檔案，方便除錯
        html_file_path = f'{self.working_directory}/hermes_ebus_taipei_route_list.html'
        with open(html_file_path, "w", encoding="utf-8") as file:
            file.write(self.content)
        print(f"✅ 路線列表頁面 HTML 已儲存至: {html_file_path}")

    def parse_route_list(self) -> pd.DataFrame:
        """
        從抓取的 HTML 內容中解析公車路線 ID 和名稱。
        """
        # 使用正規表達式匹配路線 ID 和名稱
        pattern = r'<li><a href="javascript:go\(\'(.*?)\'\)">(.*?)</a></li>'
        matches = re.findall(pattern, self.content, re.DOTALL)

        if not matches:
            raise ValueError("❌ 未找到任何路線資料，請檢查網頁結構或正規表達式。")

        # 將匹配結果轉換為 DataFrame
        bus_routes = [(route_id, route_name.strip()) for route_id, route_name in matches]
        self.dataframe = pd.DataFrame(bus_routes, columns=["route_id", "route_name"])
        print(f"✅ 成功解析 {len(self.dataframe)} 條路線資料。")
        return self.dataframe

    def save_to_database(self):
        """
        將解析後的公車路線資料儲存到 SQLite 資料庫。
        """
        print("正在將路線列表儲存至資料庫...")
        for _, row in self.dataframe.iterrows():
            # 使用 merge 插入或更新資料
            self.session.merge(bus_route_orm(route_id=row['route_id'], route_name=row['route_name']))
        self.session.commit()
        print("✅ 路線列表已儲存至資料庫。")

    def read_from_database(self) -> pd.DataFrame:
        """
        從 SQLite 資料庫讀取公車路線資料。
        """
        print("正在從資料庫讀取路線列表...")
        query = self.session.query(bus_route_orm)
        df = pd.read_sql(query.statement, self.session.bind)
        print(f"✅ 從資料庫讀取到 {len(df)} 條路線。")
        return df

    def set_route_data_updated(self, route_id: str, status: int = 1):
        """
        更新資料庫中特定路線的處理狀態。
        status: 0=未處理, 1=已成功處理, 2=處理異常。
        """
        self.session.query(bus_route_orm).filter_by(route_id=route_id).update({"route_data_updated": status})
        self.session.commit()

    def __del__(self):
        """
        物件銷毀時關閉資料庫會話和引擎。
        """
        self.session.close()
        self.engine.dispose()


class taipei_route_info:
    """
    管理特定公車路線和方向的站點資料抓取、解析和儲存。
    """
    def __init__(self, route_id: str, direction: str, working_directory: str = 'data'):
        self.route_id = route_id
        self.direction = direction # 'go' (去程) 或 'come' (回程)
        self.working_directory = working_directory
        os.makedirs(self.working_directory, exist_ok=True)
        self.url = f'https://ebus.gov.taipei/Route/StopsOfRoute?routeid={route_id}'
        self.content = None

        if self.direction not in ['go', 'come']:
            raise ValueError("Direction 參數必須是 'go' (去程) 或 'come' (回程)")
        
        # 抓取特定路線的站點頁面內容
        self._fetch_content()

    def _fetch_content(self):
        """
        使用 Playwright 抓取特定路線的站點頁面 HTML 內容，並根據方向點擊按鈕。
        """
        print(f"  正在抓取路線 {self.route_id} ({'去程' if self.direction == 'go' else '回程'}) 的站點資料...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url)

            # 如果是回程，點擊回程按鈕
            if self.direction == 'come':
                # 假設回程按鈕的 CSS 選擇器為 'a.stationlist-come-go-gray.stationlist-come'
                # 請根據實際網頁結構確認此選擇器是否正確
                try:
                    page.click('a.stationlist-come-go-gray.stationlist-come', timeout=5000)
                    page.wait_for_timeout(1000) # 給予時間讓頁面內容更新
                except Exception as e:
                    print(f"  ❌ 點擊回程按鈕失敗或未找到按鈕: {e}")
                    # 如果回程按鈕不存在或點擊失敗，可能該路線沒有回程，或選擇器有誤
                    # 在這種情況下，我們將嘗試繼續解析當前頁面內容 (通常會是去程)
            
            page.wait_for_timeout(3000) # 等待頁面載入和渲染
            self.content = page.content()
            browser.close()
        # 這裡不儲存個別路線的 HTML，因為最終目標是 Excel 輸出，且可能處理大量檔案
        # 可以根據除錯需求取消註釋以下程式碼來儲存 HTML
        # with open(f'{self.working_directory}/ebus_taipei_{self.route_id}_{self.direction}.html', "w", encoding="utf-8") as file:
        #    file.write(self.content)


    def parse_route_info(self) -> pd.DataFrame:
        """
        從抓取的 HTML 內容中解析公車站點的詳細資訊。
        """
        # 為了只獲取站名，修改正規表達式。這裡假設站名在 auto-list-stationlist-place 類別中。
        # 原本的 pattern 會抓取多個資訊，我們只關注站名和站序。
        pattern = re.compile(
            r'<li>.*?<span class="auto-list-stationlist-position.*?">(.*?)</span>\s*' # 到站資訊，雖然不需要但為了匹配結構保留
            r'<span class="auto-list-stationlist-number">\s*(\d+)</span>\s*' # 站序
            r'<span class="auto-list-stationlist-place">(.*?)</span>.*?' # 站名
            r'<input[^>]+name="item\.UniStopId"[^>]+value="(\d+)"[^>]*>.*?' # stop_id，雖然不需要但為了匹配結構保留
            r'<input[^>]+name="item\.Latitude"[^>]+value="([\d\.]+)"[^>]*>.*?' # latitude，雖然不需要但為了匹配結構保留
            r'<input[^>]+name="item\.Longitude"[^>]+value="([\d\.]+)"[^>]*>', # longitude，雖然不需要但為了匹配結構保留
            re.DOTALL
        )
        matches = pattern.findall(self.content)

        if not matches:
            print(f"  ❌ 路線 {self.route_id} ({'去程' if self.direction == 'go' else '回程'}) 未找到站點資料。")
            return pd.DataFrame() # 返回空的 DataFrame

        # 這裡我們只取 'stop_number' 和 'stop_name'
        # matches 的每個元素是一個 tuple，包含 arrival_info, stop_number, stop_name, stop_id, latitude, longitude
        parsed_data = []
        for match in matches:
            stop_number = int(match[1])  # 站序
            stop_name = match[2].strip() # 站名
            parsed_data.append({'stop_number': stop_number, 'stop_name': stop_name})

        self.dataframe = pd.DataFrame(parsed_data)
        self.dataframe["direction"] = self.direction
        self.dataframe["route_id"] = self.route_id
        
        print(f"  ✅ 路線 {self.route_id} ({'去程' if self.direction == 'go' else '回程'}) 成功解析 {len(self.dataframe)} 個站點。")
        return self.dataframe

    def save_to_database(self, engine, Base):
        """
        將解析後的公車站點資料儲存到 SQLite 資料庫。
        這裡接收 engine 和 Base 參數，以便重用主程式的資料庫連接，避免重複建立。
        """
        # 由於需求是只匯出 Excel，不需要儲存所有詳細資料到 bus_stop_orm
        # 因此此方法可選擇性地簡化或移除，但為了保持結構，暫時保留並讓它執行
        # 但實際上，如果你只需要 Excel 輸出且不關心資料庫中 bus_stop_orm 的完整性，
        # 則可以省略此方法中的儲存邏輯，只在記憶體中處理 DataFrame。
        Base.metadata.create_all(engine) # 確保表格存在
        Session = sessionmaker(bind=engine)
        session = Session()

        for _, row in self.dataframe.iterrows():
            # 這裡只儲存站序、站名、方向和路線ID，其他欄位由於原始需求不需要，可以設為預設值或None
            # 注意：bus_stop_orm 的 primary_key 是 stop_number, direction, route_id
            # 如果 stop_id, arrival_info, latitude, longitude 必須有值，你需要決定如何處理它們
            # 為了讓資料庫寫入正常，我將它們設為預設值或 null。
            session.merge(bus_stop_orm(
                stop_id=None, # 不需要的資訊，可設定為 None 或預設值
                arrival_info="", # 不需要的資訊，可設定為空字串或 None
                stop_number=row["stop_number"],
                stop_name=row["stop_name"],
                latitude=0.0, # 不需要的資訊，可設定為 0.0 或 None
                longitude=0.0, # 不需要的資訊，可設定為 0.0 或 None
                direction=row["direction"],
                route_id=row["route_id"]
            ))

        session.commit()
        session.close()

# --- 主執行區塊 ---
if __name__ == "__main__":
    print("--- 開始抓取大台北公車所有路線站點資料 ---")

    # 1. 抓取所有路線列表
    route_list_manager = taipei_route_list()
    route_list_manager.parse_route_list()
    route_list_manager.save_to_database()

    # 從資料庫讀取所有路線，以便遍歷抓取詳細資訊
    all_routes_df = route_list_manager.read_from_database()
    
    # 準備一個列表來儲存所有抓取到的站點數據
    all_stops_dataframes = []

    # 獲取資料庫引擎和 Base 以傳遞給 taipei_route_info
    db_engine = route_list_manager.engine
    # 這裡的 Base 應該是之前定義的那個，無需重新定義
    # Base = declarative_base() # 在這裡重新定義一個 Base 會導致 ORM 映射問題

    # 2. 遍歷所有路線，抓取去程和回程站點
    for index, route_row in all_routes_df.iterrows():
        route_id = route_row['route_id']
        route_name = route_row['route_name'] # 獲取路線名稱以供打印

        print(f"\n>>>> 正在處理路線: {route_name} (ID: {route_id}) <<<<")

        # 處理去程 (direction = 'go')
        try:
            route_info_go = taipei_route_info(route_id, direction="go")
            df_go = route_info_go.parse_route_info()
            if not df_go.empty:
                df_go['route_name'] = route_name # 添加路線名稱
                df_go['direction_text'] = '去程' # 添加去回程文字
                all_stops_dataframes.append(df_go)
                # 將去程資料儲存到資料庫 (可選，根據需求保留或簡化 save_to_database)
                route_info_go.save_to_database(db_engine, Base) 
            else:
                print(f"  ℹ️ 路線 {route_name} (ID: {route_id}) 去程無站點資料或解析失敗。")

        except Exception as e:
            print(f"  ❌ 處理路線 {route_name} (ID: {route_id}) 去程時發生錯誤: {e}")
            route_list_manager.set_route_data_updated(route_id, status=2) # 標記為異常
            # 繼續處理回程，即使去程出錯也不中斷

        # 處理回程 (direction = 'come')
        try:
            route_info_come = taipei_route_info(route_id, direction="come")
            df_come = route_info_come.parse_route_info()
            if not df_come.empty:
                df_come['route_name'] = route_name # 添加路線名稱
                df_come['direction_text'] = '回程' # 添加去回程文字
                all_stops_dataframes.append(df_come)
                # 將回程資料儲存到資料庫 (可選，根據需求保留或簡化 save_to_database)
                route_info_come.save_to_database(db_engine, Base)
            else:
                print(f"  ℹ️ 路線 {route_name} (ID: {route_id}) 回程無站點資料或解析失敗。")

        except Exception as e:
            print(f"  ❌ 處理路線 {route_name} (ID: {route_id}) 回程時發生錯誤: {e}")
            route_list_manager.set_route_data_updated(route_id, status=2) # 標記為異常
            # 繼續處理下一條路線，不中斷

        # 如果去程和回程都處理成功，則更新路線狀態為已完成
        # 注意：這裡的 df_go 和 df_come 在 try-except 外面可能無法訪問其狀態
        # 所以更安全的做法是檢查 all_stops_dataframes 中是否有該 route_id 的資料
        # 簡化判斷邏輯，只要有資料加入就標記成功
        if any(df['route_id'].eq(route_id).any() for df in all_stops_dataframes if not df.empty):
             route_list_manager.set_route_data_updated(route_id, status=1)
             print(f"✅ 路線 {route_name} (ID: {route_id}) 資料處理完畢。")
        else:
             print(f"⚠️ 路線 {route_name} (ID: {route_id}) 去程和回程均無有效資料。")


    # 3. 合併所有站點數據並匯出到 Excel
    if all_stops_dataframes:
        final_dataframe = pd.concat(all_stops_dataframes, ignore_index=True)
        output_excel_path = f"{route_list_manager.working_directory}/taipei_all_bus_routes_stops_simplified.xlsx"
        
        # 調整列順序，只保留路線名稱、站序、站名和方向
        desired_columns_order = [
            'route_name', 'direction_text', 'stop_number', 'stop_name'
        ]
        # 確保所有列都在 final_dataframe 中，如果沒有則會被忽略
        final_dataframe = final_dataframe[
            [col for col in desired_columns_order if col in final_dataframe.columns]
        ]

        final_dataframe.to_excel(output_excel_path, index=False)
        print(f"\n--- 任務完成 ---")
        print(f"✅ 所有公車路線的站點資料已匯出至 Excel 檔案: {output_excel_path}")
        print(f"總共匯出 {len(final_dataframe)} 條站點記錄。")
    else:
        print("\n--- 任務完成 ---")
        print("❌ 未抓取到任何有效的站點資料，未生成 Excel 檔案。")

    # 關閉初始的 route_list_manager，確保資料庫連線關閉
    del route_list_manager