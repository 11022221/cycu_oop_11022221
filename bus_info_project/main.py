import pandas as pd

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
    finder = BusRouteFinder("HW2.csv")
    print("🚌 歡迎使用台北市公車查詢系統")
    origin = input("請輸入出發站（中文）：").strip()
    destination = input("請輸入目的站（中文）：").strip()

    # 找出包含出發站與目的站的有效路線
    routes = finder.find_routes(origin, destination)

    if not routes:
        print("❌ 找不到符合的路線。請確認站名是否正確，且目的站應在出發站之後。")
        return

    # 顯示路線資訊
    for route in routes:
        route_name = route['route_name']
        direction = route['direction_text']
        stops = route['stops']

        print(f"\n🚌 路線：{route_name}（{direction}）")
        print(f"經過站：{' → '.join(stops)}")
        print("-" * 40)

if __name__ == "__main__":
    main()