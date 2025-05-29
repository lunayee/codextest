import serial
import threading
from filepath import fileControl
import time
from concurrent.futures import ThreadPoolExecutor
from nemadict import customNemaJson
import random


class RudderSys:
    def __init__(self, port, baudrate=9600, timeout=1, enginID=-9999):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.rudder_ser = None
        self.file = fileControl()
        self.step = 0
        self.mode = "FUMode"
        self.enginID = enginID
        self.filename = (
            "01_Data/02_RudderSys/"
            + str(self.file.timestr(timstr="d"))
            + "_"
            + str(self.enginID)
            + ".csv"
        )
        self.rawdata = {
            "enginID": enginID,
            "RudderOrder": "0",
            "RudderFeedback": "0",
            "Pilot_Mode": "None",
            "Heading": "0",
            "Course": "0",
        }
        # test
        self.decision = 0
        self.currudder = 0
        self.control_thread = None
        self.stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(
            max_workers=2
        )  # 創建一個最大工作數為1的線程池
        # 用於接收數據的線程池
        self.receive_executor = ThreadPoolExecutor(max_workers=1)
        self.receive_stop_event = threading.Event()
        self.receiveTime = time.time()

    def open(self):
        try:
            if self.rudder_ser is not None:
                print(f"串口 {self.port} 已經打開")
                return True
            else:
                self.rudder_ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                )
                if self.rudder_ser.is_open:
                    # 開始接收值
                    self.receive_executor.submit(self._receive_data_loop)
                    print(f"串口 {self.port} 已打開")
                    return True
        except serial.SerialException as e:
            self.rudder_ser = None
            print(f"無法打開串口 {self.port}: {e}")
            return False

    def close(self):
        self.file.close()
        if self.rudder_ser and self.rudder_ser.is_open:
            self.rudder_ser.close()
            print(f"串口 {self.port} 已關閉")

        if not self.receive_executor._shutdown:
            self.receive_stop_event.set()
            self.receive_executor.shutdown(wait=True)

        if not self.executor._shutdown:
            self.executor.shutdown(wait=True)

    # 發送指令的方法
    def send_AutopilotSdbyMode(self):
        command = b"AutopilotSdbyMode"
        self.rudder_ser.write(command)
        self.mode = "SdbyMode"

    def send_AutopilotAutoMode(self):
        command = b"AutopilotAutoMode"
        self.rudder_ser.write(command)
        self.mode = "AutoMode"

    def send_AutoStOneDeg(self):
        command = b"AutoStOneDeg"
        self.rudder_ser.write(command)

    def send_AutoPortOneDegC(self):
        command = b"AutoPortOneDeg"
        self.rudder_ser.write(command)

    def send_AutopilotFUMode(self):
        command = b"AutopilotFUMode"
        self.rudder_ser.write(command)
        self.mode = "FUMode"

    def send_FUStbOneDeg(self):
        command = b"FUStbOneDeg"
        self.rudder_ser.write(command)

    def send_FUPortOneDeg(self):
        command = b"FUPortOneDeg"
        self.rudder_ser.write(command)

    def connect(self):
        # 簡易的連結判斷，之後要考慮如果serial斷掉怎麼辦
        return 0 if self.rudder_ser is None else 1

    def Adjustment(self, adjVal):
        self.decision = adjVal
        self.currudder = adjVal
        self.step = adjVal
        # print(f"[動作] 舵角校準成功")

    # 接收數據的方法
    def receive_data(self):
        # 使用線程池執行 `_process_receive_data`
        self.receive_executor.submit(self._process_receive_data)

    def _receive_data_loop(self):
        # 持續運行，直到 `receive_stop_event` 被設置
        while not self.receive_stop_event.is_set():
            self._process_receive_data()

    def _process_receive_data(self):

        if self.rudder_ser and self.rudder_ser.is_open:
            # data = "$RudderFeedback,40"
            # data = self.rudder_ser.read(size)
            # 彥陞調整
            if time.time() - self.receiveTime > 25:
                self.receiveTime = time.time()
                self.rudder_ser.flushInput()

            data = (
                str(self.rudder_ser.readline())
                .replace("'", "")
                .replace("b", "")
                .replace("\\r\\n", "")
            )

            raw = customNemaJson().formatjson(data)
            # print("89898989898",data,raw)
            if raw is not None:
                self.rawdata.update(raw)
                result = f"{time.time()},{self.enginID},{data}"
                # result = time.time() + "," + str(self.enginID) + "," + data
                self.file.writefile(
                    "01_Data/01_Receive/RudderSys/"
                    + str(self.file.timestr(timstr="d"))
                    + "_"
                    + str(self.enginID)
                    + ".csv",
                    str(result),
                    method="csv",
                )
                return raw
            return None
        else:
            # print("串口尚未打開或已關閉")
            return None

    def controlRudder(self, decision=0):
        # print(f"[DEBUG] 嘗試控制舵角, 指令: {decision}")

        # if self.executor is None:
        #     print("[ERROR] executor 是 None，可能被垃圾回收！")
        #     return

        # if self.executor._shutdown:
        #     print("[ERROR] executor 已關閉，無法提交任務")
        #     return

        # print("[DEBUG] executor 仍然活著，提交舵機控制指令")

        # 中斷當前線程
        if self.control_thread is not None:
            self.stop_event.set()  # 設置停止事件
            self.control_thread.result()  # 等待線程結束
            # self.control_thread = None  # 清空線程引用

        # 清除中斷標記
        self.stop_event.clear()

        # 使用線程池執行任務
        self.control_thread = self.executor.submit(
            self._control_rudder_thread, decision
        )

    def _control_rudder_thread(self, decision=0):
        # curangle = self.decision  # 獲取當前舵角
        self.decision = decision  # 更新舵角
        step = abs(self.step - decision)

        def update_rudder(command_func, command_str, increment):
            # start = time.time()
            for _ in range(int(step)):
                if self.stop_event.is_set():  # 檢查是否收到中斷信號
                    msg = f"enginID:{self.enginID},舵角被中斷"
                    print(msg)
                    return msg
                if self.rudder_ser is not None:
                    try:
                        command_func()  # 執行指令
                    except Exception as e:
                        self.controlRudder(decision=0)
                        print(f"[CRITICAL] 未知錯誤: {e}，將舵角歸零...")
                        self.file.writefile(
                            "01_Data/99_Error/RudderSys/"
                            + str(self.file.timestr(timstr="d"))
                            + ".csv",
                            str(e),
                            method="csv",
                        )

                self.currudder += increment
                self.step += increment
                # print(self.enginID, "目前舵角", self.currudder)
                result = f"{self.enginID},{self.currudder},{command_str}"
                self.file.writefile(self.filename, str(result), method="csv")
                time.sleep(0.08)
            # end = time.time()
            # print("舵角動作完成時間",end-start,"step:" ,step, "send_command:",command_str,"enginID:" ,self.enginID,"decision:" ,decision)

            return command_str

        if self.mode == "FUMode":
            if decision < self.currudder:
                update_rudder(self.send_FUPortOneDeg, "FUPortOneDeg", -1)
            elif decision > self.currudder:
                update_rudder(self.send_FUStbOneDeg, "FUStbOneDeg", 1)
            else:
                self.file.writefile(self.filename, "Nochange", method="csv")
                # print(self.enginID, "舵角不變")
        else:
            if self.stop_event.is_set():  # 檢查是否收到中斷信號
                print("decision", decision, "被中斷")
                return
            print("模式切換成FUMode")
            self.mode = self.send_AutopilotFUMode()
            time.sleep(0.3)


# 使用範例
if __name__ == "__main__":
    # 開啟串口
    rudder_system = RudderSys(port="COM11", enginID=0)
    rudder_system.open()  #

    # # 發送指令
    # rudder_system.send_AutopilotSdbyMode() #待機模式
    # rudder_system.send_AutopilotAutoMode() #AUTO模式
    # rudder_system.send_AutoStOneDeg() #往右設定維持航道度數
    # rudder_system.send_AutoPortOneDegC() #往左設定維持航道度數
    # rudder_system.send_AutopilotFUMode() #Follow-up模式

    # time.sleep(0.1)
    # rudder_system.send_FUStbOneDeg() #右舵一度
    # rudder_system.send_FUPortOneDeg() #左舵一度

    # # 接收數據
    # while(1):
    #     received_data = rudder_system.receive_data()
    #     print("runrunrun")
    #     if received_data:
    #         print(f"收到的數據: {received_data}")

    # # 關閉串口
    # rudder_system.close()

    # 校準
    rudder_system.Adjustment(adjVal=1)
    # # 控制(decision為角度值)
    rudder_system.controlRudder(decision=-19)
    # rudder_system.controlRudder(decision=-25)
    # time.sleep(2)
    rudder_system.controlRudder(decision=9)
