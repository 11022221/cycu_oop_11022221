# -*- coding: utf-8 -*-
"""
Retrieves Taipei eBus route and stop data, stores it in SQLite, and optionally saves HTML for inspection.
"""

import os
import re
import enum
import logging
import pandas as pd
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, Column, String, Float, Integer, Enum
from sqlalchemy.orm import sessionmaker, declarative_base

# 設定日誌紀錄
logging.basicConfig(filename='ebus_error.log', level=logging.ERROR, format='%(asctime)s - %(message)s')

# ORM 設定
Base = declarative_base()

class RouteStatus(enum.Enum):
    pending = 0
    updated = 1
    failed = 2

class RouteORM(Base):
    __tablename__ = 'data_route_list'
    route_id = Column(String, primary_key=True)
    route_name = Column(String)
    route_data_updated = Column(Enum(RouteStatus), default=RouteStatus.pending)

class StopORM(Base):
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
    def __init__(self, working_directory='data'):
        self.working_directory = working_directory
        os.makedirs(self.working_directory, exist_ok=True)
        self.url = 'https://ebus.gov.taipei/ebus?ct=all'
        self.content = None
        self._fetch_content()

        self.engine = create_engine(f'sqlite:///{self.working_directory}/hermes_ebus_taipei.sqlite3')
        self.engine.connect()
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def _fetch_content(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url)
            page.wait_for_timeout(3000)
            self.content = page.content()
            browser.close()

        html_file_path = f'{self.working_directory}/hermes_ebus_taipei_route_list.html'
        with open(html_file_path, "w", encoding="utf-8") as file:
            file.write(self.content)

    def parse_route_list(self):
        pattern = r'<li><a href="javascript:go\(\'(.*?)\'\)">(.*?)</a></li>'
        matches = re.findall(pattern, self.content, re.DOTALL)
        if not matches:
            raise ValueError("No data found for route table")
        bus_routes = [(route_id, route_name.strip()) for route_id, route_name in matches]
        self.dataframe = pd.DataFrame(bus_routes, columns=["route_id", "route_name"])
        return self.dataframe

    def save_to_database(self):
        for _, row in self.dataframe.iterrows():
            self.session.merge(RouteORM(route_id=row['route_id'], route_name=row['route_name']))
        self.session.commit()

    def read_from_database(self):
        df = pd.read_sql(self.session.query(RouteORM).statement, self.session.bind)
        return df

    def set_route_status(self, route_id, status: RouteStatus):
        self.session.query(RouteORM).filter_by(route_id=route_id).update({"route_data_updated": status})
        self.session.commit()

    def __del__(self):
        self.session.close()
        self.engine.dispose()


class taipei_route_info:
    def __init__(self, route_id, direction='go', working_directory='data', save_html=False):
        self.route_id = route_id
        self.direction = direction
        self.content = None
        self.url = f'https://ebus.gov.taipei/Route/StopsOfRoute?routeid={route_id}'
        self.working_directory = working_directory
        self.save_html = save_html

        if self.direction not in ['go', 'come']:
            raise ValueError("Direction must be 'go' or 'come'")

        self._fetch_content()

    def _fetch_content(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.url)

            if self.direction == 'come':
                page.click('a.stationlist-come-go-gray.stationlist-come')

            page.wait_for_timeout(3000)
            self.content = page.content()
            browser.close()

        if self.save_html:
            html_file = f"{self.working_directory}/ebus_taipei_{self.route_id}_{self.direction}.html"
            with open(html_file, "w", encoding="utf-8") as file:
                file.write(self.content)

    def parse_route_info(self):
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
            raise ValueError(f"No data found for route ID {self.route_id}")

        self.dataframe = pd.DataFrame(matches, columns=[
            "arrival_info", "stop_number", "stop_name", "stop_id", "latitude", "longitude"
        ])
        self.dataframe["direction"] = self.direction
        self.dataframe["route_id"] = self.route_id
        self.dataframe["latitude"] = self.dataframe["latitude"].astype(float)
        self.dataframe["longitude"] = self.dataframe["longitude"].astype(float)
        self.dataframe["stop_number"] = self.dataframe["stop_number"].astype(int)
        return self.dataframe

    def save_to_database(self):
        engine = create_engine(f"sqlite:///{self.working_directory}/hermes_ebus_taipei.sqlite3")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        for _, row in self.dataframe.iterrows():
            session.merge(StopORM(
                stop_id=row["stop_id"],
                arrival_info=row["arrival_info"],
                stop_number=row["stop_number"],
                stop_name=row["stop_name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                direction=row["direction"],
                route_id=row["route_id"]
            ))
        session.commit()
        session.close()


if __name__ == "__main__":
    route_list = taipei_route_list()
    route_list.parse_route_list()
    route_list.save_to_database()

    # 從資料庫自動抓取未處理的路線
    pending_routes = route_list.read_from_database()
    bus_list = pending_routes[pending_routes['route_data_updated'] == 'pending']['route_id'].tolist()

    for route_id in bus_list:
        try:
            route_info = taipei_route_info(route_id, direction="go", save_html=True)
            route_info.parse_route_info()
            route_info.save_to_database()

            print(f"\n[Route ID: {route_id}]")
            for index, row in route_info.dataframe.iterrows():
                print(f"Stop #{row['stop_number']}: {row['stop_name']} (Lat: {row['latitude']}, Lon: {row['longitude']})")

            route_list.set_route_status(route_id, RouteStatus.updated)
        except Exception as e:
            print(f"[Error] Route {route_id} failed: {e}")
            logging.error(f"Route {route_id} failed with error: {e}")
            route_list.set_route_status(route_id, RouteStatus.failed)
