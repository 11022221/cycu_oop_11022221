import sys
sys.stdout.reconfigure(encoding='utf-8')
from ebus_taipei import taipei_route_list, taipei_route_info

if __name__ == "__main__":
    # Initialize and process route data
    route_list = taipei_route_list()
    route_list.parse_route_list()
    route_list.save_to_database()

    bus1='0161000900' #承德幹線
    bus2='0161001500' #基隆幹線

    bus_list = [bus1]


    for route_id in bus_list:
        try:
            route_info = taipei_route_info(route_id, direction="go")
            route_info.parse_route_info()
            route_info.save_to_database()


            for index, row in route_info.dataframe.iterrows():
                print(f"Stop Number: {row['stop_number']}, Stop Name: {row['stop_name']}, "
                      f"Latitude: {row['latitude']}, Longitude: {row['longitude']}")

            # route_info = taipei_route_info(route_id, direction="come")
            # route_info.parse_route_info()
            # route_info.save_to_database()

            route_list.set_route_data_updated(route_id)
            print(f"Route data for {route_id} updated.")

        except Exception as e:
            print(f"Error processing route {route_id}: {e}")
            route_list.set_route_data_unexcepted(route_id)
            continue