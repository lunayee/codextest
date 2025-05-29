import numpy as np
import math
import scipy.linalg # type: ignore
from pyproj import Proj
import time

class Cal_Rudder_Engine:
    def __init__(self,):
        # 記錄上一個航向值 (預設為 0)
        self.last_heading = None
        self.last_time = time.time()

    def calculate_target_heading(self,lat, lon, lat_ref, lon_ref):
        proj = Proj(proj="utm", zone=51, ellps="WGS84", datum="WGS84")
        x1, y1 = proj(lon, lat)
        x2, y2 = proj(lon_ref, lat_ref)
        theta = math.atan2(x2 - x1, y2 - y1)
        azimuth = (math.degrees(theta) + 360) % 360
        return azimuth

    def calculate_heading_difference(self,current_heading, target_heading):
        difference = (target_heading - current_heading + 180) % 360 - 180
        return difference

    def calculate_distance(self,lat1, lon1, lat2, lon2):
        proj = Proj(proj="utm", zone=51, ellps="WGS84", datum="WGS84")
        x1, y1 = proj(lon1, lat1)
        x2, y2 = proj(lon2, lat2)
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    def calculate_yaw_rate(self, current_heading):
        """計算偏航率 (Yaw Rate) = 航向變化量 / 時間變化量"""
        current_time = time.time()
        delta_t = current_time - self.last_time  # 計算時間間隔
        if delta_t > 0:
            yaw_rate = (current_heading - self.last_heading) / delta_t  # 偏航率 (°/s)
        else:
            yaw_rate = 0
        return yaw_rate


    def RudderAngleCalculation(self,current_heading,target_heading, yaw_rate):
        A = np.array([[0.9521, 0.0479], [1, 0]])
        B = np.array([[-0.2043], [0]])
        Q = np.array([[5, 0], [0, 1]])
        R = np.array([[23]])
        P = scipy.linalg.solve_discrete_are(A, B, Q, R)
        K = np.linalg.inv(R + B.T @ P @ B) @ (B.T @ P @ A)

        yaw_error = self.calculate_heading_difference(current_heading, target_heading)
        X = np.array([[yaw_error], [yaw_rate]])
        delta = -K @ X
        delta_value_limited = int(max(min(delta[0, 0], 25), -25))
        return delta_value_limited, target_heading, yaw_error

    def EngineCalculation(self,now_gps, target_point):
        distance = self.calculate_distance(now_gps[0], now_gps[1], target_point[0], target_point[1])
        if distance >= 250:
            return 1.8
        elif distance >= 150:
            return 1.5
        elif distance >= 100:
            return 1.3
        elif distance >= 80:
            return 1
        elif distance > 0:
            return 0.6
        else:
            return 0

# ========== 測試範例 ==========
if __name__ == "__main__":
    cal_rudder_engine = Cal_Rudder_Engine()
    ship_data = {
        "Heading": 359,       # 初始航向（東）
    }
    
    
    # 模擬時間流動
    new_heading = 10# 假設船舶 1 秒後航向變為 95°
    
    # 計算偏航率
    yaw_rate = cal_rudder_engine.calculate_yaw_rate(new_heading)
    # 計算舵角
    rudder_angle, target_heading, yaw_error = cal_rudder_engine.RudderAngleCalculation(ship_data['Heading'], new_heading, yaw_rate)
    
    print(f"新偏航率: {yaw_rate:.2f} 度/秒")
    print(f"計算舵角: {rudder_angle} 度")
    print(f"目標航向: {target_heading:.2f} 度")
    print(f"偏航誤差: {yaw_error:.2f} 度")
    # print(f"引擎輸出: {engine_power:.2f}")
