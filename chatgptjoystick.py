import asyncio
import re
import requests
import serial_asyncio
import numpy as np
from enum import Enum, unique

@unique
class Mode(Enum):
    NEUTRAL = 0                    # 不動
    FORWARD = 1                    # 前進
    BACKWARD = 2                   # 後退
    TRANSLATION_RIGHT = 3          # 右平移
    TRANSLATION_LEFT = 4           # 左平移
    ROTATE_CLOCKWISE = 5           # 順時針
    ROTATE_COUNTERCLOCKWISE = 6    # 逆時針
    CONNECTED = 900
    CALLSTATION = 901
    CLOSE = 999

    def __str__(self):
        mapping = {
            Mode.NEUTRAL: "neutral",
            Mode.FORWARD: "forward",
            Mode.BACKWARD: "backward",
            Mode.TRANSLATION_RIGHT: "Translation_Right",
            Mode.TRANSLATION_LEFT: "Translation_Left",
            Mode.ROTATE_CLOCKWISE: "Rotate_Clockwise",
            Mode.ROTATE_COUNTERCLOCKWISE: "Rotate_CounterClockwise",
            Mode.CONNECTED: "connected",
            Mode.CALLSTATION: "Callstation",
            Mode.CLOSE: "close",
        }
        return mapping[self]

class JoystickSys:
    # 定義各模式之間允許的狀態轉換：
    VALID_TRANSITIONS = {
        Mode.NEUTRAL: [
            Mode.FORWARD, Mode.BACKWARD, Mode.TRANSLATION_RIGHT,
            Mode.TRANSLATION_LEFT, Mode.ROTATE_CLOCKWISE, Mode.ROTATE_COUNTERCLOCKWISE,
            Mode.CONNECTED, Mode.CALLSTATION
        ],
        Mode.FORWARD: [Mode.NEUTRAL],
        Mode.BACKWARD: [Mode.NEUTRAL],
        Mode.TRANSLATION_RIGHT: [Mode.NEUTRAL],
        Mode.TRANSLATION_LEFT: [Mode.NEUTRAL],
        Mode.ROTATE_CLOCKWISE: [Mode.NEUTRAL],
        Mode.ROTATE_COUNTERCLOCKWISE: [Mode.NEUTRAL],
        Mode.CONNECTED: [Mode.NEUTRAL, Mode.CALLSTATION],
        Mode.CALLSTATION: [Mode.NEUTRAL],
        # Mode.CLOSE 可依需求新增轉換規則
    }

    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reader = None
        self.writer = None

        # 儲存從 Serial 接收到的資料
        self.pdata = []
        self.current_mode = Mode.NEUTRAL  # 初始模式為 neutral
        self.last_counter = None          # 用來檢查資料是否為最新
        self.joystickstate = {
            'NEUTRAL_LED': '0',
            'ACTIVE_LED': '0',
            'SYNC_LED': '0',
            'LPS_L_vol': '0',
            'LPS_R_vol': '0',
        }
        # 最新控制指令，格式：(command, left_speed, left_rudder, right_speed, right_rudder)
        self.latest_command = None

        # 模式與對應的處理函式映射
        self.movement_function_mapping = {
            Mode.NEUTRAL: self._process_neutral,
            Mode.FORWARD: self._process_forward,
            Mode.BACKWARD: self._process_backward,
            Mode.ROTATE_CLOCKWISE: self._process_rotate_clockwise,
            Mode.ROTATE_COUNTERCLOCKWISE: self._process_rotate_counterclockwise,
            Mode.TRANSLATION_RIGHT: self._process_translation_right,
            Mode.TRANSLATION_LEFT: self._process_translation_left,
            Mode.CONNECTED: self._process_connected,
            # Mode.CALLSTATION 與 Mode.CLOSE 可依需求擴充
        }

    #=== Serial 連線管理 ===#
    async def open(self):
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port, baudrate=self.baudrate
            )
            print(f"[INFO] 串口 {self.port} 已打開")
        except Exception as e:
            print(f"[ERROR] 無法打開串口 {self.port}: {e}")

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            print(f"[INFO] 串口 {self.port} 已關閉")

    #=== API 通訊與狀態更新 ===#
    async def send_control_command_periodically(self):
        """每 0.5 秒檢查最新指令並發送 API"""
        while True:
            if self.latest_command:
                command = self.latest_command[0]
                print("=== [DEBUG] 發送指令 ===", self.latest_command)
                # 根據不同模式發送對應 API 指令
                if command == Mode.NEUTRAL.value:
                    self._send_api({'Command': Mode.NEUTRAL.value})
                elif command < 900:
                    self._send_api({
                        'Command': 666,
                        'Left_Speed': self.latest_command[1],
                        'Left_Rudder': self.latest_command[2],
                        'Right_Speed': self.latest_command[3],
                        'Right_Rudder': self.latest_command[4],
                        'Range': 0.05,
                    })
                elif command == Mode.CONNECTED.value:
                    self._send_api({'Command': Mode.CONNECTED.value})
                    # 自動發送 CALLSTATION 指令
                    self._send_api({'Command': Mode.CALLSTATION.value})
                else:
                    self._send_api({'Command': command})
            await asyncio.sleep(0.5)

    def _send_api(self, jsondata: dict):
        url = "http://127.0.0.1:5899/control"
        try:
            response = requests.post(url, json=jsondata)
            if response.status_code != 200:
                print(f"請求失敗，狀態碼：{response.status_code}")
                print("錯誤訊息：", response.text)
        except Exception as e:
            print(f"發送 API 時發生錯誤: {e}")
        self._update_data()

    def _update_data(self):
        url = "http://127.0.0.1:5899/status"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                self.joystickstate = response.json()["Voltage"]["rawdata"]
            else:
                print(f"狀態更新失敗，狀態碼：{response.status_code}")
                print("錯誤訊息：", response.text)
        except Exception as e:
            print(f"更新狀態時發生錯誤: {e}")

    #=== Serial 資料讀取與解析 ===#
    async def read_and_process_serial_data(self):
        while True:
            try:
                raw = await self.reader.readline()
                if raw:
                    self.pdata = await self.parse_data(raw)
                    if self.pdata and self._is_valid_data(self.pdata):
                        # 根據解析資料計算最新控制指令
                        self.latest_command = self._process_movement(self.pdata['raw_decimal'])
            except Exception as e:
                print(f"[ERROR] Serial 讀取錯誤: {e}")
                break

    async def parse_data(self, raw: bytes) -> dict:
        if raw:
            decoded = raw.decode(errors='ignore').strip()
            match = re.search(r'ID:\s+(0x[0-9A-Fa-f]+).*?DATA:\s+([\d\s]+)', decoded)
            if match:
                can_id = match.group(1)
                data_values = [int(x) for x in match.group(2).split()]
                return {"ID": can_id, "raw_decimal": data_values}
            else:
                print("[WARNING] 無法解析數據:", decoded)
                return None
        else:
            print("[WARNING] raw 沒有值")
            return None

    def _is_valid_data(self, data: dict) -> bool:
        raw = data.get("raw_decimal", [])
        if len(raw) < 8:
            print("[WARNING] 資料長度不符，跳過")
            return False
        counter = raw[7]
        if self.last_counter is not None:
            diff = (counter - self.last_counter) % 256
            if diff == 0 or diff > 200:
                return False
        self.last_counter = counter
        return True

    #=== 向量化輔助函式 ===#
    def _symmetric_vector(self, value: float) -> np.ndarray:
        """利用 NumPy 建立一個向量 [value, -value]"""
        return np.array([value, -value])

    #=== 各模式的處理函式 ===#
    def _process_neutral(self, raw_decimal: list):
        return (Mode.NEUTRAL.value, 0, 0, 0, 0)

    def _process_forward(self, raw_decimal: list):
        mod16 = raw_decimal[1] % 16
        mod32 = raw_decimal[1] % 32
        left_speed = self._calculate_lever(raw_decimal[3])
        right_speed = self._calculate_lever(raw_decimal[3])
        if mod16 == 5 or mod32 == 5:
            left_rudder = -self._calculate_rudder(raw_decimal[2])
            right_rudder = -self._calculate_rudder(raw_decimal[2])
        elif mod16 == 9 or mod32 == 9:
            left_rudder = self._calculate_rudder(raw_decimal[2])
            right_rudder = self._calculate_rudder(raw_decimal[2])
        else:
            left_rudder = right_rudder = 0
        return (Mode.FORWARD.value, left_speed, left_rudder, right_speed, right_rudder)

    def _process_backward(self, raw_decimal: list):
        mod16 = raw_decimal[1] % 16
        mod32 = raw_decimal[1] % 32
        left_speed = -self._calculate_back_lever(raw_decimal[3])
        right_speed = -self._calculate_back_lever(raw_decimal[3])
        if mod16 == 10 or mod32 == 10:
            left_rudder = self._calculate_rudder(raw_decimal[2])
            right_rudder = self._calculate_rudder(raw_decimal[2])
        elif mod16 == 6 or mod32 == 6:
            left_rudder = -self._calculate_rudder(raw_decimal[2])
            right_rudder = -self._calculate_rudder(raw_decimal[2])
        else:
            left_rudder = right_rudder = 0
        return (Mode.BACKWARD.value, left_speed, left_rudder, right_speed, right_rudder)

    def _process_rotate_clockwise(self, raw_decimal: list):
        rotation_val = self._calculate_rotation_lever(raw_decimal[4])
        rudder_val = self._calculate_rudder(raw_decimal[4])
        speed_vec = self._symmetric_vector(rotation_val)
        rudder_vec = self._symmetric_vector(rudder_val)
        left_speed, right_speed = speed_vec
        left_rudder, right_rudder = rudder_vec
        return (Mode.ROTATE_CLOCKWISE.value, float(left_speed), float(left_rudder), float(right_speed), float(right_rudder))

    def _process_rotate_counterclockwise(self, raw_decimal: list):
        rotation_val = self._calculate_rotation_lever(raw_decimal[4])
        rudder_val = self._calculate_rudder(raw_decimal[4])
        speed_vec = self._symmetric_vector(rotation_val)
        rudder_vec = self._symmetric_vector(rudder_val)
        # 反轉速度向量表示左右對調（或取負）
        speed_vec = -speed_vec
        left_speed, right_speed = speed_vec
        left_rudder, right_rudder = rudder_vec
        return (Mode.ROTATE_COUNTERCLOCKWISE.value, float(left_speed), float(left_rudder), float(right_speed), float(right_rudder))

    def _process_translation_right(self, raw_decimal: list):
        left_speed = self._calculate_translation_lever(raw_decimal[2])
        right_speed = -left_speed
        return (Mode.TRANSLATION_RIGHT.value, left_speed, -25, right_speed, 25)

    def _process_translation_left(self, raw_decimal: list):
        right_speed = self._calculate_translation_lever(raw_decimal[2])
        left_speed = -right_speed
        return (Mode.TRANSLATION_LEFT.value, left_speed, -25, right_speed, 25)

    def _process_connected(self, raw_decimal: list):
        return (Mode.CONNECTED.value, 0, 0, 0, 0)

    def _default_movement(self, raw_decimal: list):
        print("未定義的模式")
        return (Mode.NEUTRAL.value, 0, 0, 0, 0)

    def _process_movement(self, raw_decimal: list):
        # 根據 raw_decimal 與 joystick 狀態更新模式
        self._update_mode(raw_decimal)
        mode = self.current_mode
        process_func = self.movement_function_mapping.get(mode, self._default_movement)
        return process_func(raw_decimal)

    #=== 模式更新與切換 ===#
    def _update_mode(self, raw_decimal: list):
        # 依據 raw_decimal 與 joystick 狀態決定模式變換
        if self.joystickstate["ACTIVE_LED"] == "1":
            if raw_decimal[2] == 0 and raw_decimal[3] == 0 and raw_decimal[4] == 0:
                self.change_mode(Mode.NEUTRAL)
            elif raw_decimal[1] % 16 in (1, 5, 9) or raw_decimal[1] % 32 in (1, 5, 9):
                self.change_mode(Mode.FORWARD)
            elif raw_decimal[1] % 16 in (2, 6, 10) or raw_decimal[1] % 32 in (2, 6, 10):
                self.change_mode(Mode.BACKWARD)
            elif raw_decimal[1] == 16:
                self.change_mode(Mode.ROTATE_CLOCKWISE)
            elif raw_decimal[1] == 32:
                self.change_mode(Mode.ROTATE_COUNTERCLOCKWISE)
            elif raw_decimal[1] % 16 == 8 or raw_decimal[1] % 32 == 8:
                self.change_mode(Mode.TRANSLATION_RIGHT)
            elif raw_decimal[1] % 16 == 4 or raw_decimal[1] % 32 == 4:
                self.change_mode(Mode.TRANSLATION_LEFT)
        else:
            if raw_decimal[5] == 8:
                self.change_mode(Mode.CONNECTED)
            elif raw_decimal[2] == 0 and raw_decimal[3] == 0 and raw_decimal[4] == 0:
                self.change_mode(Mode.NEUTRAL)

    def change_mode(self, target_mode: Mode) -> bool:
        """
        嘗試切換到 target_mode 模式：
        若當前模式已為 target_mode 則不進行切換，
        否則必須符合 VALID_TRANSITIONS 中的轉換規則才會切換，
        否則印出錯誤提示並返回 False。
        """
        if self.current_mode == target_mode:
            return False
        allowed = self.VALID_TRANSITIONS.get(self.current_mode, [])
        if target_mode in allowed:
            self.current_mode = target_mode
            print(f"模式切換為 {str(target_mode)}")
            return True
        else:
            # print(f"無法從 {str(self.current_mode)} 切換到 {str(target_mode)}，請先回到 {str(Mode.NEUTRAL)} 模式")
            return False

    #=== 線性計算輔助函式 ===#
    def _calculate_linear(self, value: float, m: float, b: float, decimals: int = 2) -> float:
        return round(m * value + b, decimals)

    def _calculate_lever(self, value: float) -> float:
        return self._calculate_linear(value, 0.009, 0.6)

    def _calculate_back_lever(self, value: float) -> float:
        return self._calculate_linear(value, 0.006, 0.6)

    def _calculate_rudder(self, value: float) -> int:
        return int(round(0.25 * value))

    def _calculate_rotation_lever(self, value: float) -> float:
        return self._calculate_linear(value, 0.004, 0.6)

    def _calculate_translation_lever(self, value: float) -> float:
        return self._calculate_linear(value, 0.006, 0.6)

    #=== 主循環 ===#
    async def main_loop(self):
        await self.open()
        await asyncio.gather(
            self.read_and_process_serial_data(),
            self.send_control_command_periodically(),
            asyncio.Event().wait()  # 保持程式持續運行
        )

async def main():
    joystick = JoystickSys(port="COM4")
    await joystick.main_loop()

if __name__ == "__main__":
    asyncio.run(main())
