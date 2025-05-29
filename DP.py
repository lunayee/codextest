import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# 環境初始化
fig, ax = plt.subplots(figsize=(10, 20))
ax.set_facecolor('cyan')
dock_color = 'lightgray'

# # 碼頭碰撞區域
# dock_collision_zones = [
#     {"x_min": 0, "x_max": 10, "y_min": 18, "y_max": 20},  # 主碼頭
#     {"x_min": 5, "x_max": 5.5, "y_min": 16, "y_max": 18},  # 側碼頭1
#     {"x_min": 3, "x_max": 3.5, "y_min": 16, "y_max": 18}   # 側碼頭2
# ]

# # 碼頭繪製
# main_dock = plt.Rectangle((0, 18), 10, 2, color=dock_color)
# side_dock = plt.Rectangle((5, 15), 0.5, 3, color=dock_color)
# side_dock2 = plt.Rectangle((3, 15), 0.5, 3, color=dock_color)
# ax.add_patch(main_dock)
# ax.add_patch(side_dock)
# ax.add_patch(side_dock2)

# 定義碼頭碰撞區域和繪製參數
dock_collision_zones = [
    {"x_min": 0, "x_max": 10, "y_min": 18, "y_max": 20, "color": dock_color},  # 主碼頭
    {"x_min": 5, "x_max": 5.5, "y_min": 15, "y_max": 18, "color": dock_color},  # 側碼頭1
    {"x_min": 3, "x_max": 3.5, "y_min": 15, "y_max": 18, "color": dock_color}   # 側碼頭2
]

# 碼頭繪製
for zone in dock_collision_zones:
    dock_rectangle = plt.Rectangle(
        (zone["x_min"], zone["y_min"]),  # 左下角座標
        zone["x_max"] - zone["x_min"],  # 寬度
        zone["y_max"] - zone["y_min"],  # 高度
        color=zone["color"]             # 填充顏色
    )
    ax.add_patch(dock_rectangle)
# 地圖邊界
ax.set_xlim(0, 10)
ax.set_ylim(0, 20)

# 船隻參數
ship_length = 8.9 / 10  # 比例調整到10x20地圖
ship_width = 2.6 / 10
ship_position = [10, 10]  # 初始位置 (x, y)
ship_angle = 0  # 初始角度
speed = 0.01  # 初始速度
max_speed = 0.1  # 最大前進速度
reverse_speed = -0.1  # 最大後退速度
acceleration = 0.002  # 加速度
deceleration_distance = 1.5  # 減速開始的距離
is_reversing = False  # 是否後退狀態
# 設定最大角速度
max_angular_speed = 25  # 每幀最大改變的角度 (度)
# 泊位目標點
target_point = [(3.5 + 5) / 2, 17.5]  # 泊位中間點

# 泊位區域（可視化）
dock_boundaries = {
    "x_min": 3.5,  # 左泊位邊界
    "x_max": 5,    # 右泊位邊界
    "y_min": 16.5,    # 泊位底部邊界
    "y_max": 18   # 泊位頂部邊界
}
dock_boundary_rect = plt.Rectangle(
    (dock_boundaries["x_min"], dock_boundaries["y_min"]),
    dock_boundaries["x_max"] - dock_boundaries["x_min"],
    dock_boundaries["y_max"] - dock_boundaries["y_min"],
    edgecolor='red',
    facecolor='none',
    linestyle='--',
    linewidth=2
)
ax.add_patch(dock_boundary_rect)



# 繪製目標點
ax.plot(target_point[0], target_point[1], 'go', label="Target Point")  # 綠色圓點表示目標點

# 繪製船隻
ship = plt.Polygon([
    (ship_position[0] - ship_length / 2, ship_position[1] - ship_width / 2),
    (ship_position[0] + ship_length / 2, ship_position[1] - ship_width / 2),
    (ship_position[0] + ship_length / 2, ship_position[1] + ship_width / 2),
    (ship_position[0] - ship_length / 2, ship_position[1] + ship_width / 2)
], color='blue', alpha=0.7)
ax.add_patch(ship)

# 計算船頭與目標點的角度
def calculate_angle(ship_pos, target):
    dx = target[0] - ship_pos[0]
    dy = target[1] - ship_pos[1]
    return np.degrees(np.arctan2(dy, dx))

# 確認船隻是否與碼頭碰撞
def check_dock_collision(corners, zones):
    for zone in zones:
        for corner in corners:
            x, y = corner
            if zone["x_min"] <= x <= zone["x_max"] and zone["y_min"] <= y <= zone["y_max"]:
                return True  # 船隻角點進入碼頭區域
    return False

# 判定船隻是否到達泊位
def is_docked(ship_pos, target, angle, dock_angle=90, tolerance=0.5):
    # 計算與目標點的距離
    distance = np.sqrt((ship_pos[0] - target[0])**2 + (ship_pos[1] - target[1])**2)
    # 計算與泊位角度的差值
    angle_diff = abs(angle - dock_angle)
    # 判定是否在泊位範圍內
    in_dock_area = (dock_boundaries["x_min"] <= ship_pos[0] <= dock_boundaries["x_max"] and
                    dock_boundaries["y_min"] <= ship_pos[1] <= dock_boundaries["y_max"])
    
    # # 動態打印調試資訊
    # print(f"Distance to target: {distance:.2f}, Angle diff: {angle_diff:.2f}, In dock: {in_dock_area}")

    # 判定條件：在泊位範圍內，距離小於容許範圍，角度誤差小於容許範圍
    return in_dock_area and distance < tolerance and angle_diff < 10

# 計算船頭與最近障礙物的距離
def calculate_obstacle_distance(ship_front, obstacles):
    min_distance = float('inf')
    for obs in obstacles:
        x_min, x_max, y_min, y_max = obs["x_min"], obs["x_max"], obs["y_min"], obs["y_max"]
        # 計算船頭與障礙物四條邊的最小距離
        if x_min <= ship_front[0] <= x_max:
            dx = 0
        else:
            dx = min(abs(ship_front[0] - x_min), abs(ship_front[0] - x_max))
        if y_min <= ship_front[1] <= y_max:
            dy = 0
        else:
            dy = min(abs(ship_front[1] - y_min), abs(ship_front[1] - y_max))
        distance = np.hypot(dx, dy)
        min_distance = min(min_distance, distance)
    return min_distance

# 更新船隻位置和角度
def update(frame):
    global ship_position, ship_angle, speed, is_reversing

    # 計算船頭需要調整的角度
    desired_angle = calculate_angle(ship_position, target_point)
    angle_diff = desired_angle - ship_angle

    # 計算與目標點的距離
    distance_to_target = np.hypot(target_point[0] - ship_position[0], target_point[1] - ship_position[1])

    # 計算船頭的位置
    angle_rad = np.radians(ship_angle)
    ship_front = [ship_position[0] + ship_length / 2 * np.cos(angle_rad),
                  ship_position[1] + ship_length / 2 * np.sin(angle_rad)]

    # 計算船頭與障礙物的最小距離
    obstacle_distance = calculate_obstacle_distance(ship_front, dock_collision_zones)

    # 如果船頭距離障礙物小於 0.3 公尺，觸發後退模式
    if obstacle_distance < 0.3 and not is_reversing:
        print(f"Obstacle detected at distance: {obstacle_distance:.2f}. Reversing!")
        is_reversing = True
        speed = reverse_speed  # 後退速度

    # 後退模式邏輯
    if is_reversing:
        # 計算與最近障礙物的角度
        obstacle_positions = []
        for obs in dock_collision_zones:
            # 計算障礙物中心位置
            obs_center = [(obs["x_min"] + obs["x_max"]) / 2, (obs["y_min"] + obs["y_max"]) / 2]
            obstacle_positions.append(obs_center)

        # 找到最近的障礙物
        distances = [np.hypot(ship_position[0] - obs_pos[0], ship_position[1] - obs_pos[1]) for obs_pos in obstacle_positions]
        min_index = np.argmin(distances)
        closest_obstacle_pos = obstacle_positions[min_index]

        # 計算與最近障礙物和目標點的角度
        obstacle_angle = calculate_angle(ship_position, closest_obstacle_pos)
        target_angle = calculate_angle(ship_position, target_point)

        # 判斷障礙物相對於船隻的左右位置
        angle_to_obstacle = (obstacle_angle - ship_angle + 360) % 360
        angle_to_target = (target_angle - ship_angle + 360) % 360

        # 判斷轉向方向
        if angle_to_obstacle > 0 and angle_to_obstacle < 180:
            # 障礙物在船隻右側，向左轉
            turn_direction = 1
        else:
            # 障礙物在船隻左側，向右轉
            turn_direction = -1

        # 調整船隻角度
        ship_angle += turn_direction * max_angular_speed * 0.1  # 調整轉向速度，可根據需要修改係數
        ship_angle %= 360  # 確保角度在 0-360 度之間

        # 當船尾遠離障礙物一定距離，恢復前進模式
        ship_back = [ship_position[0] - ship_length / 2 * np.cos(angle_rad),
                     ship_position[1] - ship_length / 2 * np.sin(angle_rad)]
        back_obstacle_distance = calculate_obstacle_distance(ship_back, dock_collision_zones)
        if back_obstacle_distance > 3:  # 根據需要調整閾值
            print("Obstacle cleared. Resuming forward movement.")
            is_reversing = False
            speed = 0.02  # 恢復前進速度

    else:
        # 前進模式下的速度調整
        if distance_to_target > deceleration_distance:
            speed = min(speed + acceleration, max_speed)  # 加速
        else:
            speed = max(speed - acceleration, 0.02)  # 減速

        # 調整船隻角度朝向目標點
        angle_diff = (desired_angle - ship_angle + 180) % 360 - 180  # 調整角度差為 [-180, 180]
        angle_correction = np.clip(angle_diff, -max_angular_speed, max_angular_speed)
        ship_angle += angle_correction
        ship_angle %= 360  # 確保角度在 0-360 度之間

    # 移動船隻
    ship_position[0] += speed * np.cos(np.radians(ship_angle))
    ship_position[1] += speed * np.sin(np.radians(ship_angle))

    # 更新船隻的多邊形繪圖
    rotation_matrix = np.array([
        [np.cos(np.radians(ship_angle)), -np.sin(np.radians(ship_angle))],
        [np.sin(np.radians(ship_angle)),  np.cos(np.radians(ship_angle))]
    ])
    corners = np.array([
        [-ship_length / 2, -ship_width / 2],
        [ ship_length / 2, -ship_width / 2],
        [ ship_length / 2,  ship_width / 2],
        [-ship_length / 2,  ship_width / 2]
    ])
    rotated_corners = np.dot(corners, rotation_matrix.T) + ship_position

    # 判定是否撞到碼頭
    if check_dock_collision(rotated_corners, dock_collision_zones):
        print("Collision detected with dock!")
        ani.event_source.stop()

    # 判定是否停泊完成
    if is_docked(ship_position, target_point, ship_angle):
        print("Docking successful!")
        ani.event_source.stop()

    ship.set_xy(rotated_corners)
    return ship,



# 動畫
ani = FuncAnimation(fig, update, frames=2000, interval=50, blit=True)

plt.title("Ship Docking Simulation with Reverse Function")
plt.xlabel("X-Axis (meters)")
plt.ylabel("Y-Axis (meters)")
plt.legend()
plt.show()
