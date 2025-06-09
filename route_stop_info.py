import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from interactive_bus_info import taipei_route_info, get_route_id_by_name

class BusRouteFinder:
    def __init__(self, csv_file):
        """初始化，讀取靜態資料 (HW2.csv)"""
        self.df = pd.read_csv(csv_file)

    def find_routes(self, origin, destination):
        """尋找包含出發站與目的站的有效路線"""
        results = []
        for (route_name, direction), group in self.df.groupby(['route_name', 'direction_text']):
            stops = group.sort_values('stop_number')['stop_name'].tolist()
            if origin in stops and destination in stops:
                if stops.index(origin) < stops.index(destination):
                    results.append({
                        'route_name': route_name,
                        'direction_text': direction,
                        'stops': stops[stops.index(origin):stops.index(destination)+1]
                    })
        return results

def main():
    # 初始化資料庫連線
    engine = create_engine('sqlite:///data/taipei_bus.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    # 載入公車路線資料
    finder = BusRouteFinder("C:/Users/jack/OneDrive/文件/GitHub/cycu_oop_11022221/HW2.csv")  # 更新為完整路徑
    print("🚌 歡迎使用台北市公車查詢系統")
    origin = input("請輸入出發站（中文）：").strip()
    destination = input("請輸入目的站（中文）：").strip()

    # 找出包含出發站與目的站的有效路線
    routes = finder.find_routes(origin, destination)

    if not routes:
        print("❌ 找不到符合的路線。請確認站名是否正確，且目的站應在出發站之後。")
        return

    # 顯示路線資訊並查詢到站資訊
    for route in routes:
        route_name = route['route_name']
        direction = route['direction_text']
        stops = route['stops']

        print(f"\n🚌 路線：{route_name}（{direction}）")
        print(f"經過站：{' → '.join(stops)}")
        print("-" * 40)

        # 查詢到站資訊
        route_id = get_route_id_by_name(route_name, session)
        if not route_id:
            print(f"❌ 找不到名稱為「{route_name}」的公車路線 ID。")
            continue

        try:
            route_info = taipei_route_info(route_id, 'go' if direction == '去程' else 'come')
            route_info.fetch_route_info()
            df = route_info.parse_route_info()

            # 僅輸出使用者輸入的兩個站名的到站資訊
            filtered_df = df[df["stop_name"].isin([origin, destination])]
            if filtered_df.empty:
                print("❌ 未找到任何到站資訊。")
            else:
                print("\n以下是該路線的到站資訊：")
                print(filtered_df[["stop_number", "stop_name", "arrival_info"]])
        except Exception as e:
            print(f"❌ 查詢過程中發生錯誤：{e}")

if __name__ == "__main__":
    main()