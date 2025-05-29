
import asyncio
import serial_asyncio
# from controlsys import ControlSys
import time
import requests
import json
import re

class JoystickSys:
    def __init__(self, port, baudrate=9600, timeout=1):
        # self.ControlSys=ControlSys(gear_system_port="COM11", rudder_systemEnZero_port='COM12', rudder_systemEnOne_port='COM13')
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reader = None
        self.writer = None
        # DATA
        self.pdata=[]
        self.current_mode = 0
        self.last_counter = None  # ⬅️ 新增 counter 記錄變數
        self.joystickstate = {'NEUTRAL_LED': '0', 'ACTIVE_LED': '0', 'SYNC_LED': '0','LPS_L_vol': '0', 'LPS_R_vol': '0',}
        self.mode_dict = {
            0: "neutral",       # 不動
            1: "forward",    # 前進
            2: "backward",    # 後退
            3: "Translation_Right", # 右平移
            4: "Translation_Left", # 左平移
            5: "Rotate_Clockwise", # 順時針
            6: "Rotate_CounterClockwise", #逆時針
            900:"connected",
            901:"Callstation",
            999:"close",
        }
        # **最新的指令狀態**
        self.latest_command = None
    async def open(self):
        """ 使用 asyncio 開啟 Serial 連線 """
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url=self.port, baudrate=self.baudrate
            )
            print(f"[INFO] 串口 {self.port} 已打開")
        except Exception as e:
            print(f"[ERROR] 無法打開串口 {self.port}: {e}")

    async def close(self):
        """ 關閉 Serial 連線 """
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            print(f"[INFO] 串口 {self.port} 已關閉")  

    async def send_control_command_periodically(self):
        """ 每 3 秒發送一次最新的指令 """
        while True:
            if self.latest_command:
                print("=== [DEBUG] 發送指令 ===", self.latest_command)
                if self.latest_command[0]==0:
                    # self.ControlSys.decision(Command=0)  
                    jsondata = {'Command': 0}  
                    self.send_api(jsondata)
                elif self.latest_command[0]<900:
                    # self.ControlSys.decision(
                    #     Command=666, 
                    #     Left_Speed=self.latest_command[0], 
                    #     Left_Rudder=self.latest_command[1], 
                    #     Right_Speed=self.latest_command[2], 
                    #     Right_Rudder=self.latest_command[3]
                    # )
                    jsondata = {
                    'Command': 666,
                    'Left_Speed': self.latest_command[1],
                    'Left_Rudder': self.latest_command[2],
                    'Right_Speed': self.latest_command[3],
                    'Right_Rudder': self.latest_command[4],
                    'Range':0.05,
                    }     
                    self.send_api(jsondata)
                elif self.latest_command[0] == 900:
                    jsondata = {'Command': 900}
                    self.send_api(jsondata)

                    # 自動送出 Callstation
                    jsondata_901 = {'Command': 901}
                    self.send_api(jsondata_901)    
                else:
                    # self.ControlSys.decision(Command=901)  
                    jsondata = {
                    'Command': self.latest_command[0],
                    }   
                    self.send_api(jsondata)
                    # self.joystickstate = {'NEUTRAL_LED': '0', 'ACTIVE_LED': '1', 'SYNC_LED': '0','LPS_L_vol': '0', 'LPS_R_vol': '0',}
            await asyncio.sleep(0.5)  

    def send_api(self,jsondata):
        url = "http://127.0.0.1:5899/control"
        # 要發送的資料

        data = jsondata  
        response = requests.post(url, json=data)

        # 檢查回應狀態碼和內容
        if response.status_code == 200:
            pass
            # print("伺服器回應：", json.dumps(response.json(), ensure_ascii=False))
        else:
            print(f"請求失敗，狀態碼：{response.status_code}")
            print("錯誤訊息：", response.text)

        self.update_data()
    def update_data(self):

        url = "http://127.0.0.1:5899/status"
        response = requests.get(url)
        
        # 檢查回應狀態碼和內容
        if response.status_code == 200:
            self.joystickstate = response.json()["Voltage"]["rawdata"]
            # print("伺服器回應：", json.dumps(response.json(), ensure_ascii=False))
        else:
            print(f"請求失敗，狀態碼：{response.status_code}")
            print("錯誤訊息：", response.text)
    async def read_and_process_serial_data(self):
        """ 同時讀取 Serial 資料並立即處理 """
        while True:
            try:
                raw = await self.reader.readline()  # 讀取 CAN 數據封包 (8 bytes)
                
                if raw:
                    self.pdata = await self.parse_data(raw)  # 解析數據
                    
                    
                    if self.pdata and self.is_valid_data(self.pdata):
                        
                        self.latest_command = self.movement(self.pdata['raw_decimal'])  # **直接處理最新的數據**
                        # print("7777777777777777777",self.pdata['raw_decimal'][5])
            except Exception as e:
                print(f"[ERROR] Serial 讀取錯誤: {e}")
                break  # 若發生錯誤，退出循環



    async def parse_data(self, raw):
        """ 解析 CAN 數據並轉換為字典 """
        # {'ID': '0xCFDD601', 'raw_decimal': [0, 0, 0, 0, 0, 0, 0, 168]}
        if raw:
            decoded = raw.decode(errors='ignore').strip()  # 解碼並去除換行

            # **使用正則表達式提取 CAN ID 和 DATA**
            match = re.search(r'ID:\s+(0x[0-9A-Fa-f]+).*?DATA:\s+([\d\s]+)', decoded)
            if match:
                can_id = match.group(1)  # 擷取 CAN ID
                data_values = [int(x) for x in match.group(2).split()]  # 轉換 DATA 為數字陣列
                
                # **回傳格式化數據**
                data = {
                    "ID": can_id,
                    "raw_decimal": data_values
                }
                return data
            else:
                print("[WARNING] 無法解析數據:", decoded)
                return None
        else:
            print("[WARNING] raw 沒有值")
            return None
    

    def is_valid_data(self, data):
        """ 檢查資料是否為最新且有效 """
        if data:
            raw = data["raw_decimal"]

            # 防呆：確保資料長度正確
            if len(raw) < 8:
                print("[WARNING] 資料長度不符，跳過")
                return False

            state = raw[1]
            counter = raw[7]

            # counter 檢查：確保資料是新的
            if self.last_counter is not None:
                diff = (counter - self.last_counter) % 256
                if diff == 0 or diff > 200:
                    # print(f"⏩ 舊資料或雜訊，忽略 (counter={counter}, last={self.last_counter})")
                    return False

            # ✅ 更新 last_counter
            self.last_counter = counter

            return True  
        return False  
    def _update_mode(self, raw_decimal):
        #(條件,動作指令)
        # print("叫站燈號",self.joystickstate) #要改這個
        # 
        # print(raw_decimal)
        if self.joystickstate["ACTIVE_LED"] =="1":
            conditions = [
                (raw_decimal[2] == 0 and raw_decimal[3] == 0 and raw_decimal[4] == 0, 0),
                (raw_decimal[1] % 16 in (1, 5, 9) or raw_decimal[1] % 32 in (1, 5, 9), 1),
                (raw_decimal[1] % 16 in (2, 6, 10) or raw_decimal[1] % 32 in (2, 6, 10), 2),
                (raw_decimal[1] ==16 , 5),
                (raw_decimal[1] ==32 , 6),
                (raw_decimal[1] % 16 == 8 or raw_decimal[1] % 32 == 8, 3),
                (raw_decimal[1] % 16 == 4 or raw_decimal[1] % 32 == 4, 4),
            ]
        else:
            conditions = [
                (raw_decimal[5] == 8 , 900),
                (raw_decimal[2] == 0 and raw_decimal[3] == 0 and raw_decimal[4] == 0 , 0),
            ]
        for condition, mode in conditions:
            if condition:
                self.change_mode(mode)
                return
        print("此動作還沒有定義")
    
    def movement(self,raw_decimal):
        #[0, 0, 0, 0, 0, 0, 0, 188]
        if raw_decimal:
            self._update_mode(raw_decimal)
            if self.current_mode==0 :
                left_speed = right_speed = left_rudder = right_rudder = 0
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)
            elif self.current_mode==1 :
                left_speed=self.calculate_lever(raw_decimal[3])
                right_speed=self.calculate_lever(raw_decimal[3])
                if raw_decimal[1] % 16 == 5 or raw_decimal[1] % 32 == 5:
                    left_rudder=-self.calculate_rudder(raw_decimal[2])
                    right_rudder=-self.calculate_rudder(raw_decimal[2])
                elif raw_decimal[1] % 16 == 9 or raw_decimal[1] % 32 == 9:
                    left_rudder=self.calculate_rudder(raw_decimal[2])
                    right_rudder=self.calculate_rudder(raw_decimal[2])
                else:
                    left_rudder=0
                    right_rudder=0
                
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)
            elif self.current_mode==2:
                left_speed=self.calculate_back_lever(raw_decimal[3])
                right_speed=self.calculate_back_lever(raw_decimal[3])
                left_rudder=self.calculate_rudder(raw_decimal[2])
                right_rudder=self.calculate_rudder(raw_decimal[2])
                if raw_decimal[1] % 16 == 10 or raw_decimal[1] % 32 == 10:
                    left_rudder=self.calculate_rudder(raw_decimal[2])
                    right_rudder=self.calculate_rudder(raw_decimal[2])
                elif raw_decimal[1] % 16 == 6 or raw_decimal[1] % 32 == 6:
                    left_rudder=-self.calculate_rudder(raw_decimal[2])
                    right_rudder=-self.calculate_rudder(raw_decimal[2])
                else:
                    left_rudder=0
                    right_rudder=0
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)
            elif self.current_mode==5:
                left_speed = self.calculate_rotation_lever(raw_decimal[4])
                right_speed = -self.calculate_rotation_lever(raw_decimal[4])
                left_rudder = self.calculate_rudder(raw_decimal[4])
                right_rudder = -self.calculate_rudder(raw_decimal[4]) 
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)    
            elif self.current_mode==6:       
                left_speed = -self.calculate_rotation_lever(raw_decimal[4])
                right_speed =self.calculate_rotation_lever(raw_decimal[4])
                left_rudder = self.calculate_rudder(raw_decimal[4])
                right_rudder = -self.calculate_rudder(raw_decimal[4])  
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)           
            elif self.current_mode==3:
                left_speed=self.calculate_Translation_lever(raw_decimal[2])
                right_speed = -left_speed
                left_rudder = -25
                right_rudder =25
                if raw_decimal[1] % 16 == 8 or raw_decimal[1] % 32 == 8:
                    left_rudder = -25
                    right_rudder = 25
                    right_speed = -left_speed
                elif raw_decimal[1] % 16 == 9 or raw_decimal[1] % 32 == 9:
                    left_rudder = -self.calculate_rudder_Translation_202530(9,raw_decimal[3])
                    right_rudder = self.calculate_rudder_Translation_302530(9,raw_decimal[3])
                    right_speed = -left_speed
                    left_speed = -round(-1.2 * abs(left_speed) - 0.06, 2)
                elif raw_decimal[1] % 16 == 10 or raw_decimal[1] % 32 == 10:
                    left_rudder = -self.calculate_rudder_Translation_202530(10,raw_decimal[3])
                    right_rudder = self.calculate_rudder_Translation_302530(10,raw_decimal[3])
                    right_speed = round(1.8 * -left_speed + 0.8, 2)
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder) 
            elif self.current_mode==4:
                right_speed = self.calculate_Translation_lever(raw_decimal[2])
                left_speed = -right_speed  # 預設反向補償
                left_rudder = -25
                right_rudder = 25
                if raw_decimal[1] % 16 == 4 or raw_decimal[1] % 32 == 4:
                    left_rudder = -25
                    right_rudder = 25
                    left_speed =-right_speed
                elif raw_decimal[1] % 16 == 5 or raw_decimal[1] % 32 == 5:
                    left_rudder = -self.calculate_rudder_Translation_302530(5,raw_decimal[3]) 
                    right_rudder = self.calculate_rudder_Translation_202530(5,raw_decimal[3])
                    left_speed = -right_speed
                    right_speed = -round(-1.2 * abs(right_speed) - 0.06, 2)
                elif raw_decimal[1] % 16 == 6 or raw_decimal[1] % 32 == 6:
                    left_rudder = -self.calculate_rudder_Translation_302530(6,raw_decimal[3])
                    right_rudder =self.calculate_rudder_Translation_202530(6,raw_decimal[3]) 
                    left_speed = round(1.8 * -right_speed + 0.8, 2)
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)             
            elif self.current_mode==900:
                #更換成api
                print("joystick連接")
                return self.check_mode(self.current_mode,0,0,0,0)
                
            # elif self.current_mode==901:
            #     #更換成api
            #     # print("joystick叫站")
            #     return self.check_mode(self.current_mode,0,0,0,0)
            else:
                print("此動作還沒有定義")                
                return self.check_mode(0,0,0,0,0)
            
        else:
            print("pdata沒有值")
            return None
        
    def calculate_lever(self, value):
        m = 0.009
        b = 0.6
        return round(m * value + b,2)

    def calculate_back_lever(self, value):
        m = 0.006
        b = 0.6
        return round(m * value + b,2)
        
    def calculate_rudder(self, value):
        m = 0.25
        b = 0
        return round(m * value + b)
        
    def calculate_rotation_lever(self, value):
        m = 0.004
        b = 0.6
        return round(m * value + b,2)

    def calculate_Translation_lever(self, value):
        m = 0.006
        b = 0.6
        return round(m * value + b,2)

    def calculate_rudder_Translation_2025(self, value):
        m = 0.05
        b = 20
        return round(m * value + b)
    
    def calculate_rudder_Translation_2530(self, value):
        m = 0.1
        b = 25
        return round(m * value + b)

    def calculate_rudder_Translation_302530(self, digit, value):
        coefficients = {
            4: (1, 25),
            5: (0.05, 25),
            6: (0.05, 25),
            8: (1, 25),
            9: (0.05, 25),
            10: (0.05, 25),
        }
        return self.calculate_value(digit, value, coefficients)    
    
    def calculate_rudder_Translation_202530(self, digit, value):
        coefficients = {
            4: (1, 25),
            5: (-0.05, 25),
            6: (0.05, 25),
            8: (1, 25),
            9: (-0.05, 25),
            10: (0.05, 25),
        }
        return self.calculate_value(digit, value, coefficients)
    
    def calculate_value(self, digit, value, coefficients):
        if digit in coefficients:
            m, b = coefficients[digit]
            return m * value + b
        print("無效的值")
        return 0
    
    def check_mode(self,command, left_speed, left_rudder, right_speed, right_rudder):
        if self.current_mode == 0:  # neutral 模式
            return command,0, 0, 0, 0
        elif self.current_mode == 1:  # forward 模式
            left_speed = left_speed
            right_speed = right_speed
        elif self.current_mode == 2:  # backward 模式
            left_speed = -left_speed
            right_speed = -right_speed
        elif self.current_mode in [5, 6]:  # Rotate 模式
            pass
        # print(f"command={command}, left_speed={left_speed}, left_rudder={left_rudder}, right_speed={right_speed}, right_rudder={right_rudder}")
        return command,left_speed, left_rudder, right_speed, right_rudder
        
    # 判斷當前狀態並決定是否切換模式
    def change_mode(self, target_mode):
        if self.current_mode == target_mode:
            # print(f"模式未變更，仍為 {self.mode_dict[target_mode]}")
            return False
        valid_transitions = {
            0: [1, 2, 3, 4, 5, 6,900,901],  # neutral 可切換到所有模式
            1: [0],                # forward 只能切換到 neutral
            2: [0],                # backward 只能切換到 neutral
            3: [0],                # Translation_Right 只能切換到 neutral
            4: [0],                # Translation_Left 只能切換到 neutral
            5: [0],                # Rotate_Clockwise 只能切換到 neutral
            6: [0],                 # Rotate_CounterClockwise 只能切換到 neutral
            900:[0,901],              # connected 只能切換到 Callstation
            901:[0]                 # Callstation 只能切換到 neutral
        }
        if target_mode in valid_transitions.get(self.current_mode, []):
            self.current_mode = target_mode
            print(f"模式切換為 {self.mode_dict[target_mode]}")
            return True
        else:
            # print(f"無法從 {self.mode_dict[self.current_mode]} 切換到 {self.mode_dict[target_mode]}，請先回到 neutral 模式")
            return False    
    async def main_loop(self):
        """ 主循環，確保程式一直運行 """
        await self.open()
        
        # **確保所有任務持續運行**
        await asyncio.gather(
            self.read_and_process_serial_data(),
            self.send_control_command_periodically(),  # **每 3 秒發送一次最新指令**
            asyncio.Event().wait()  # 讓程式不會直接結束
        )

# **主程式**
async def main():
    joystick = JoystickSys(port="COM4")
    await joystick.main_loop()
# 使用範例
if __name__ == "__main__":
    asyncio.run(main())
    # raw = b'\xff\x02\x00\x02\x00\x02\x00\x00\x06'
    # raw2 = b'\x02\xff\x00\x02\x00\x02\x00\x00\x06'
    原地點 = b'CAN1 MB: 7  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 0 0 0 0 0 0 203   TS: 37834\r\n'
    最下 = b'CAN1 MB: 4  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 2 0 100 0 0 0 219   TS: 43780\r\n'
    最左 = b'CAN1 MB: 4  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 4 100 0 0 0 0 103   TS: 34819\r\n'
    最前 = b'CAN1 MB: 5  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 1 0 100 0 0 0 194   TS: 10111\r\n'
    最右 = b'CAN1 MB: 7  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 8 100 0 0 0 0 223   TS: 34807\r\n'
    最右旋轉 = b'CAN1 MB: 6  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 16 0 0 100 0 0 58   TS: 34393\r\n'
    最左旋轉 = b'CAN1 MB: 7  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 32 0 0 100 0 0 121   TS: 24141\r\n'
    按A鈕 = b'CAN1 MB: 6  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 0 0 0 0 1 0 22   TS: 19026\r\n'
    按Boost鈕 = b'CAN1 MB: 7  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 0 0 0 0 2 0 55   TS: 21479\r\n'
    按c鈕 = b'CAN1 MB: 6  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 0 0 0 0 4 0 249   TS: 11287\r\n'
    按Tackcommand鈕 = b'CAN1 MB: 6  ID: 0xCFDD601  EXT: 1  LEN: 8 DATA: 0 0 0 0 0 8 0 176   TS: 25297\r\n'
    # system.ControlSys.decision(Command=666,Left_Speed=1.2,Left_Rudder=10,Right_Speed=-1.2,Right_Rudder=-10)
    
        #     self.mode_dict = {
        #     0: "neutral",       # 不動
        #     1: "forward",    # 前進
        #     2: "backward",    # 後退
        #     3: "Translation_Right", # 右平移
        #     4: "Translation_Left", # 左平移
        #     5: "Rotate_Clockwise", # 順時針
        #     6: "Rotate_CounterClockwise", #逆時針
        #     900:"connected",
        #     901:"Callstation",
        #     999:"close",
        # }