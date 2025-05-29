import asyncio
import serial_asyncio
# from controlsys import ControlSys
import time
import requests
import json
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
                    'Range':0.01,
                    }     
                    self.send_api(jsondata)
                    
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
                raw = await self.reader.readexactly(9)  # 每次讀取 9 bytes
                print("444444444444444",raw)
                if raw:
                    self.pdata = await self.parse_data(raw)  # 解析數據
                    if self.pdata:
                        self.latest_command = self.movement(self.pdata)  # **直接處理最新的數據**
            except Exception as e:
                print(f"[ERROR] Serial 讀取錯誤: {e}")
                break  # 若發生錯誤，退出循環



    async def parse_data(self,raw):
        if raw:
            if raw[0]==255:
                raw_decimal = [byte for byte in raw]
                return raw_decimal
            else:
                # **清除 Serial Buffer**
                try:
                    await self.reader.read(20)  # 讀取剩餘的 Buffer
                    print("[INFO] Serial 緩存已清空")
                except Exception as e:
                    print(f"[ERROR] 清除 Serial 緩存失敗: {e}")
                
                return None
        else:
            print("raw沒有值")
            return None
    def calculate_value(self, digit, value, coefficients):
        if digit in coefficients:
            m, b = coefficients[digit]
            return m * value + b
        print("無效的值")
        return 0
    
    def calculate_lever(self, digit, value):
        coefficients = {
            3: (0.0018711, 1.08),
            2: (0.0011309, 0.6019),
            1: (0.00106383, -0.771276596),
            0: (0.00093033, -1.009574468),
        }
        return self.calculate_value(digit, value, coefficients)
    
    def calculate_rudder(self, digit, value):
        coefficients = {
            2: (0.058, 0.058),
            1: (0.057, -15.11),
            3: (0.058, 14.96),
            0: (0.050, -27.94),
        }
        return self.calculate_value(digit, value, coefficients)
        
    def calculate_rotation_lever(self, digit, value):
        coefficients = {
            2: (0.0008316, 0.6008),
            1: (-0.001, 0.805),
            3: (0.0008316, 0.8137),
            0: (-0.00087, 1.029),
        }
        return self.calculate_value(digit, value, coefficients)

    def calculate_Translation_lever(self, digit, value):
        coefficients = {
            2: (0.001247,0.601247),
            1: (-0.00125, 0.91875),
            3: (0.001247,0.92058),
            0: (-0.00125, 1.23875),
        }
        return self.calculate_value(digit, value, coefficients)

    # def calculate_Translation_lever_202530(self, digit, value):
    #     coefficients = {
    #         2: (0.000831601,0.600831601),
    #         1: (-0.000833333, 0.8125),
    #         3: (0.000831151,0.813721414),
    #         0: (0.00072974, 0.813333333),
    #     }
    #     return self.calculate_value(digit, value, coefficients)

    def calculate_rudder_Translation_202530(self, digit, value):
        coefficients = {
            2: (-0.01039501, 24.98960499),
            1: (-0.01041667, 27.66664501),
            3: (-0.01039501, 22.32848233),
            0: (-0.00910948, 29.99997834),
        }
        return self.calculate_value(digit, value, coefficients)
    
    def calculate_rudder_Translation_302530(self, digit, value):
        coefficients = {
            2: (0.01039501, 25.01039501),
            1: (-0.01041667, 27.65625),
            3: (0.01039501, 27.67151767),
            0: (0.01041667, 27.66666667),
        }
        return self.calculate_value(digit, value, coefficients)
    
    def _update_mode(self, pdata):
        #(條件,動作指令)
        # print("叫站燈號",self.joystickstate) #要改這個
        if self.joystickstate["ACTIVE_LED"] =="1":
            conditions = [
                (pdata[2] == 0 and pdata[4] == 0 and pdata[6] == 0, 0),
                (pdata[1] >= 2 and pdata[2] != 0, 1),
                (pdata[1] < 2 and pdata[2] != 0, 2),
                (pdata[5] >= 2 and pdata[6] != 0, 5),
                (pdata[5] < 2 and pdata[6] != 0, 6),
                (pdata[3] >= 2 and pdata[4] != 0, 3),
                (pdata[3] < 2 and pdata[4] != 0, 4),
            ]
        else:
            conditions = [
                (pdata[2] == 0 and pdata[4] == 0 and pdata[6] == 0, 0),
                (pdata[5] >= 2 and pdata[6] != 0, 900),
                (pdata[1] >= 2 and pdata[2] != 0, 901),
            ]
        for condition, mode in conditions:
            if condition:
                self.change_mode(mode)
                return
        print("此動作還沒有定義")
    
    def movement(self,pdata):
        if pdata:
            self._update_mode(pdata)

            if self.current_mode==0 :
                left_speed = right_speed = left_rudder = right_rudder = 0
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)
            elif self.current_mode==1 :
                left_speed=round(self.calculate_lever(pdata[1],pdata[2]),2)
                right_speed=round(self.calculate_lever(pdata[1],pdata[2]),2)
                left_rudder=round(self.calculate_rudder(pdata[3],pdata[4]))
                right_rudder=round(self.calculate_rudder(pdata[3],pdata[4]))
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)
            elif self.current_mode==2:
                left_speed=round(self.calculate_lever(pdata[1],pdata[2]),2)
                right_speed=round(self.calculate_lever(pdata[1],pdata[2]),2)
                left_rudder=round(self.calculate_rudder(pdata[3],pdata[4]))
                right_rudder=round(self.calculate_rudder(pdata[3],pdata[4]))
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)
            elif self.current_mode==5:
                left_speed = round(self.calculate_rotation_lever(pdata[5],pdata[6]),2)
                right_speed = -round(self.calculate_rotation_lever(pdata[5],pdata[6]),2)
                left_rudder = round(self.calculate_rudder(pdata[5],pdata[6]))
                right_rudder = -round(self.calculate_rudder(pdata[5],pdata[6]))  
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)    
            elif self.current_mode==6:       
                left_speed = -round(self.calculate_rotation_lever(pdata[5],pdata[6]),2)
                right_speed = round(self.calculate_rotation_lever(pdata[5],pdata[6]),2)
                left_rudder = -round(self.calculate_rudder(pdata[5],pdata[6]))
                right_rudder = round(self.calculate_rudder(pdata[5],pdata[6]))      
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)           
            elif self.current_mode==3:
                right_speed=-round(self.calculate_Translation_lever(pdata[3],pdata[4]),2)
                if pdata[1]>2 and pdata[2]>0:
                    left_speed=-0.7143*right_speed+0.4457
                else:
                    left_speed=-0.7143*right_speed+0.1857
                left_rudder = -round(self.calculate_rudder_Translation_202530(pdata[1],pdata[2]))
                right_rudder = round(self.calculate_rudder_Translation_302530(pdata[1],pdata[2]))  
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder) 
            elif self.current_mode==4:
                left_speed=-round(self.calculate_Translation_lever(pdata[3],pdata[4]),2)
                # print("pdata[1]",pdata[1])
                if pdata[1]>2 and pdata[2]>0:
                    right_speed=-0.7143*left_speed+0.4457
                else:
                    right_speed=-0.7143*left_speed+0.1857
                left_rudder = -round(self.calculate_rudder_Translation_302530(pdata[1],pdata[2]))
                right_rudder = round(self.calculate_rudder_Translation_202530(pdata[1],pdata[2])) 
                return self.check_mode(self.current_mode,left_speed,left_rudder,right_speed,right_rudder)  
            elif self.current_mode==900:
                #更換成api
                # print("joystick連接")
                return self.check_mode(self.current_mode,0,0,0,0)
            elif self.current_mode==901:
                #更換成api
                # print("joystick叫站")
                left_speed = right_speed = left_rudder = right_rudder = 0
                return self.check_mode(self.current_mode,0,0,0,0)
            else:
                print("此動作還沒有定義")                
                return self.check_mode(0,0,0,0,0)
            
        else:
            print("pdata沒有值")
            return None
    def check_mode(self,command, left_speed, left_rudder, right_speed, right_rudder):
        if self.current_mode == 0:  # neutral 模式
            return command,0, 0, 0, 0
        elif self.current_mode == 1:  # forward 模式
            left_speed = abs(left_speed)
            right_speed = abs(right_speed)
        elif self.current_mode == 2:  # backward 模式
            left_speed = -abs(left_speed)
            right_speed = -abs(right_speed)
        elif self.current_mode in [5, 6]:  # Rotate 模式
            pass
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
    原地點 = [255, 2, 0, 2, 0, 2, 0, 0, 6]
    最下 = [255, 0, 32, 2, 0, 2, 0, 0, 36]
    最左 = [255, 2, 0, 0, 32, 2, 0, 0, 36]
    最前 = [255, 3, 224, 2, 0, 2, 0, 0, 231]
    最右 = [255, 2, 0, 3, 224, 2, 0,0, 231] 
    最右旋轉 = [255, 2, 0, 2, 0, 3, 224, 0, 231]
    最左旋轉 = [255, 2, 0, 2, 0, 0, 32, 0, 36]
    # system.ControlSys.decision(Command=666,Left_Speed=1.2,Left_Rudder=10,Right_Speed=-1.2,Right_Rudder=-10)