import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point

# 設定 GeoJSON 檔案路徑
geojson_path = 'C:/Users/User/Documents/GitHub/cycu_oop_11022221/0520/鄉(鎮、市、區)界線1140318'

# 讀取北北基桃的地圖資料
gdf = gpd.read_file(geojson_path, layer='TOWN_MOI_1140318')

# 篩選台北市、新北市、基隆市和桃園市
target_cities = ['臺北市', '新北市', '基隆市', '桃園市']
filtered_gdf = gdf[gdf['COUNTYNAME'].isin(target_cities)]

# 承德幹線的站牌資料
stations = [
    {"stop_name": "站牌1", "latitude": 25.0631, "longitude": 121.5135},
    {"stop_name": "站牌2", "latitude": 25.0680, "longitude": 121.5150},
    {"stop_name": "站牌3", "latitude": 25.0725, "longitude": 121.5175},
    {"stop_name": "站牌4", "latitude": 25.0770, "longitude": 121.5200},
    {"stop_name": "站牌5", "latitude": 25.0815, "longitude": 121.5230},
]

# 將站牌資料轉換為 GeoDataFrame
station_points = gpd.GeoDataFrame(
    stations,
    geometry=[Point(station["longitude"], station["latitude"]) for station in stations],
    crs="EPSG:4326"
)

# 繪製地圖
plt.figure(figsize=(12, 12))
ax = plt.gca()

# 繪製北北基桃的地圖
filtered_gdf.plot(ax=ax, edgecolor='black', color='lightblue', alpha=0.7, label='北北基桃地區')

# 繪製承德幹線的站牌 (點)
station_points.plot(ax=ax, color='red', marker='o', markersize=50, label='承德幹線站牌')

# 添加站牌名稱
for idx, row in station_points.iterrows():
    plt.text(row.geometry.x, row.geometry.y, row["stop_name"], fontsize=10, ha='right')

# 添加標題和標籤
plt.title('北北基桃地圖與承德幹線站牌位置', fontsize=16)
plt.xlabel('經度', fontsize=12)
plt.ylabel('緯度', fontsize=12)

# 添加圖例
plt.legend(fontsize=10)

# 顯示地圖
plt.tight_layout()
plt.show()