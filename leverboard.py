import serial
import threading
from filepath import fileControl
import time
from concurrent.futures import ThreadPoolExecutor
from nemadict import customNemaJson
import queue


class LeverSys:
    def __init__(self, port, baudrate=9600, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.gear_ser = None
        self.file = fileControl()
        self.filename = (
            "01_Data/03_LeverSys/" + str(self.file.timestr(timstr="d")) + ".csv"
        )
        self.rawdata = {
            "NEUTRAL_LED": "0",
            "ACTIVE_LED": "0",
            "SYNC_LED": "0",
            "LPS_L_vol": "0",
            "LPS_R_vol": "0",
        }
        # 左引擎預設
        self.left_curvoltval = 2.710  # 初始電壓
        self.left_decision = 0  # 初始決策值
        self.rawdata0 = {
            "EngineInstance": "0",
            "EngineSpeed": "0",
            "EngineBoostPressure": "0",
            "EngineTiltTrim": "0",
            "TransmissionGear": "0",
            "OilPressure": "0",
            "OilTemperature": "0",
            "DiscreteStatus": "0",
        }
        self.left_gear_status = "neutral"

        # 右引擎預設
        self.right_curvoltval = 2.710
        self.right_decision = 0
        self.rawdata1 = {
            "EngineInstance": "1",
            "EngineSpeed": "0",
            "EngineBoostPressure": "0",
            "EngineTiltTrim": "0",
            "TransmissionGear": "0",
            "OilPressure": "0",
            "OilTemperature": "0",
            "DiscreteStatus": "0",
        }
        self.right_gear_status = "neutral"
        # 保護機制
        self.left_executor = ThreadPoolExecutor(max_workers=1)
        self.right_executor = ThreadPoolExecutor(max_workers=1)
        self.left_control_thread = None
        self.right_control_thread = None
        self.left_stop_event = threading.Event()  # 左引擎的停止事件
        self.right_stop_event = threading.Event()  # 右引擎的停止事件
        self.left_lock = threading.Lock()
        self.right_lock = threading.Lock()
        # 用於接收數據的線程池
        self.receive_executor = ThreadPoolExecutor(max_workers=1)
        self.receive_stop_event = threading.Event()
        self.receiveTime = time.time()
        # 使用佇列
        self.command_queue = queue.Queue()
        self.command_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.command_thread.start()
        # 指令對應表
        self.commands = {
            "LPS_L_ACC": "左俥加速",
            "LPS_L_ACC_Five": "左俥加速5倍",
            "LPS_L_ACC_Ten": "左俥加速10倍",
            "LPS_L_DEC": "左俥減速",
            "LPS_L_DEC_Five": "左俥減速5倍",
            "LPS_L_DEC_Ten": "左俥減速10倍",
            "LPS_R_ACC": "右俥加速",
            "LPS_R_ACC_Five": "右俥加速5倍",
            "LPS_R_ACC_Ten": "右俥加速10倍",
            "LPS_R_DEC": "右俥減速",
            "LPS_R_DEC_Five": "右俥減速5倍",
            "LPS_R_DEC_Ten": "右俥減速10倍",
            "TH_ONLY_LONG_PRESS": "油門長按",
            "TH_ONLY_SHORT_PRESS": "油門短按",
            "STA_SEL_LONG_PRESS": "狀態選擇長按",
            "STA_SEL_SHORT_PRESS": "狀態選擇短按",
            "LPS_L_Neutral": "左俥空檔",
            "LPS_R_Neutral": "右俥空檔",
            "LPS_L_Forward": "左俥進檔",
            "LPS_R_Forward": "右俥進檔",
            "LPS_L_Reverse": "左俥退檔",
            "LPS_R_Reverse": "右俥退檔",
        }

    def open(self):
        try:
            if self.gear_ser is not None:
                print(f"串口 {self.port} 已經打開")
                return True
            else:
                self.gear_ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                )
                if self.gear_ser.is_open:
                    # 開始接收值
                    self.receive_executor.submit(self._receive_data_loop)
                    print(f"串口 {self.port} 打開")
                    return True

        except serial.SerialException as e:
            self.gear_ser = None
            print(f"無法打開串口 {self.port}: {e}")
            self.file.writefile(
                "01_Data/99_Error/LeverSys/"
                + str(self.file.timestr(timstr="d"))
                + ".csv",
                str(e),
                method="csv",
            )
            self.file.flush_buffer(
                "01_Data/99_Error/LeverSys/"
                + str(self.file.timestr(timstr="d"))
                + ".csv",
                method="csv",
            )
            return False

    def close(self):
        if self.gear_ser and self.gear_ser.is_open:
            self.gear_ser.close()
            print(f"串口 {self.port} 已關閉")

        if not self.receive_executor._shutdown:
            self.receive_stop_event.set()
            self.receive_executor.shutdown(wait=True)

        if not self.left_executor._shutdown:
            self.left_executor.shutdown(wait=True)

        if not self.right_executor._shutdown:
            self.right_executor.shutdown(wait=True)

        return True

    def send_board_command(self, command_key):
        """
        原本這裡直接呼叫 gear_ser.write()
        現在改成：把指令 key 放進佇列，讓 _process_queue() 統一發送。
        """
        self.command_queue.put(command_key)
        # print("333333333333333查看現在有多少佇列", list(self.command_queue))

    def _process_queue(self):
        """
        負責從佇列取出指令字串，然後真正呼叫 gear_ser.write()。
        """
        while True:
            command_key = self.command_queue.get()  # 取出指令
            try:
                if self.gear_ser is not None:
                    cmd_bytes = command_key.encode("utf-8")
                    self.gear_ser.write(cmd_bytes)
                    time.sleep(0.25)
                    print(f"[_process_queue] 已發送指令: {command_key}")
                else:
                    print(f"[_process_queue] 串口未開啟, 暫無法送: {command_key}")
            except Exception as e:
                # 如果在發送過程中出錯，可以視需求做錯誤處理
                print(f"[_process_queue] 指令 {command_key} 發送失敗，原因: {e}")
                self.file.writefile(
                    "01_Data/99_Error/LeverSys/"
                    + str(self.file.timestr(timstr="d"))
                    + ".csv",
                    str(e),
                    method="csv",
                )
                self.file.flush_buffer(
                    "01_Data/99_Error/LeverSys/"
                    + str(self.file.timestr(timstr="d"))
                    + ".csv",
                    method="csv",
                )
            finally:
                self.command_queue.task_done()

    def _clear_command_queue(self):
        """
        使用安全循環清空所有指令。
        """
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except queue.Empty:
                break
        # print("[動作] 指令佇列已清空")

    def Adjustment(self, enginID, adjVal=2.71):
        # 校準值
        if enginID == 0:
            self.left_curvoltval = adjVal
            self.left_decision = -2 * adjVal + 5
            # print(f"[動作] enginID : {enginID} 校準成功，電壓：{adjVal}V")
            return True
        elif enginID == 1:
            self.right_curvoltval = adjVal
            self.right_decision = -2 * adjVal + 5
            # print(f"[動作] enginID : {enginID} 校準成功，電壓：{adjVal}V")
            return True
        else:
            # print(f"[動作] enginID : {enginID} 校準失敗")
            return False

    # 單值
    def receive_data(self):
        # 使用線程池執行 `receive_data` 方法，並持續監聽
        self.receive_executor.submit(self._process_receive_data)

    # 持續值
    def _receive_data_loop(self):
        # 持續執行，直到 `receive_stop_event` 被設置
        while not self.receive_stop_event.is_set():
            self._process_receive_data()

    # 接收數據的方法
    def _process_receive_data(self):
        if self.gear_ser and self.gear_ser.is_open:
            # data = "$EngRap,1,11,22,33"
            # data = self.gear_ser.read(size)
            # 彥陞調整
            if time.time() - self.receiveTime > 25:
                # 每25秒清理一次usb阻塞
                self.receiveTime = time.time()
                self.gear_ser.flushInput()

            data = (
                str(self.gear_ser.readline())
                .replace("'", "")
                .replace("b", "")
                .replace("\\r\\n", "")
            )
            # zz = '$Lever,2731,2731'
            raw = customNemaJson().formatjson(data)
            if raw is not None:
                if raw.get("EngineInstance") == "0":
                    self.rawdata0.update(raw)
                elif raw.get("EngineInstance") == "1":
                    self.rawdata1.update(raw)
                else:
                    self.rawdata.update(raw)
                # result = data
                result = (time.time(), data)
                self.file.writefile(
                    "01_Data/01_Receive/LeverSys/"
                    + str(self.file.timestr(timstr="d"))
                    + ".csv",
                    str(result),
                    method="csv",
                )
                return raw
            else:
                return False
        else:
            # print("串口尚未打開或已關閉")
            return False

    def connect(self):
        # 簡易的連結判斷，之後要考慮如果serial斷掉怎麼辦
        return 0 if self.gear_ser is None else 1

    # main決策主要程式入口
    def controlGear(self, enginID, decision, range=0.01):
        # print(f"[DEBUG] 嘗試控制 {enginID} 號引擎, 指令: {decision}, range: {range}")

        # print("[DEBUG] left_executor 和 right_executor 仍然活著，提交任務")
        current_command = (enginID, decision, range)
        # 中斷當前線程
        if enginID == 0:

            if (
                self.left_control_thread is not None
                and self.left_control_thread.running()
            ):
                self.left_stop_event.set()  # 設置停止事件
                self.left_control_thread.result()  # 等待線程結束

            # 清除中斷標記
            self.left_stop_event.clear()
            # 使用線程池執行任務
            # 檢查 left_executor 狀態
            try:
                self.left_control_thread = self.left_executor.submit(
                    self._control_gear_thread, enginID, decision, range
                )
            except Exception as e:
                print(
                    f"[_control_gear_thread] enginID: {enginID} 發生錯誤: {e.__class__}, {str(e)}"
                )  # 輸出詳細的錯誤資訊
        elif enginID == 1:
            if (
                self.right_control_thread is not None
                and self.right_control_thread.running()
            ):
                self.right_stop_event.set()  # 設置停止事件
                self.right_control_thread.result()  # 等待線程結束
            # 清除中斷標記
            self.right_stop_event.clear()
            # 使用線程池執行任務
            self.right_control_thread = self.right_executor.submit(
                self._control_gear_thread, enginID, decision, range
            )

        else:
            print(f"[動作] enginID : {enginID} 錯誤ID")

    def _control_gear_thread(self, enginID, decision, range):
        start = time.time()
        # 取得目前引擎指令資訊
        cur_engine_command = self._engine_command(enginID)
        # 根據 decision 計算目標檔位
        new_gear_status = self._gear_status(decision)
        current_gear_status = cur_engine_command["current_gear_status"]
        volt_change = 0  # 看這之後可以調成甚麼
        if current_gear_status != new_gear_status:
            # 當檔位有改變時，先以 real_vol 或 curvoltval 作為基準值
            current_val = (
                cur_engine_command["real_vol"]
                if self.gear_ser is not None
                else cur_engine_command["curvoltval"]
            )
            # 執行檔位控制指令
            issuccess_gear_change = self._gear_change(
                enginID, current_gear_status, new_gear_status, current_val
            )
            if issuccess_gear_change:
                print(f"enginID:{enginID}, 檔位控制成功，執行速度控制指令")
                # 更新引擎指令，重新取得狀態
                new_engine_command = self._engine_command(enginID)
                # 統一取得目前電壓值
                current_volt = (
                    new_engine_command["real_vol"]
                    if self.gear_ser is not None
                    else new_engine_command["curvoltval"]
                )
                # 若有連接串口，先更新校準數值
                if self.gear_ser is not None:
                    self.Adjustment(enginID=enginID, adjVal=current_volt)
                # 計算需要的電壓變化步驟數
                step_change = self._calculate_voltage_steps(
                    decision, current_volt, range
                )

                if step_change != 0:
                    # 判斷應發送的指令與對應電壓變化量
                    send_command, volt_change = self._judge_send_command(
                        decision, current_volt, new_engine_command, range
                    )
                    self._adjust_speed(
                        step_change,
                        send_command,
                        enginID,
                        volt_change,
                        new_engine_command["stop_event"],
                        decision,
                    )
            else:
                print(f"enginID:{enginID}, 檔位控制失敗，跳過速度控制")

        else:
            # 檔位無變化，僅檢查速度（電壓）是否需要更新
            print(f"enginID:{enginID}, 檔位未變化，檢查速度變化")
            new_engine_command = self._engine_command(enginID)
            current_volt = (
                new_engine_command["real_vol"]
                if self.gear_ser is not None
                else new_engine_command["curvoltval"]
            )
            if self.gear_ser is not None:
                self.Adjustment(enginID=enginID, adjVal=current_volt)
            step_change = self._calculate_voltage_steps(decision, current_volt, range)
            if step_change != 0:
                print(f"enginID:{enginID}, 速度有變化，執行速度控制指令")
                send_command, volt_change = self._judge_send_command(
                    decision, current_volt, new_engine_command, range
                )
                self._adjust_speed(
                    step_change,
                    send_command,
                    enginID,
                    volt_change,
                    new_engine_command["stop_event"],
                    decision,
                )
            else:
                print(f"enginID:{enginID}, 檔位與速度均未變化")
        end = time.time()
        # self.file.flush_buffer("01_Data/03_LeverSys/"+ str(self.file.timestr(timstr="d")) + ".csv", method="csv")
        # caltime = (
        #     f"_control_gear_thread,{enginID},{decision},{volt_change},{start},{end}"
        # )
        # self.file.writefile(
        #     "01_Data/04_Time/" + str(self.file.timestr(timstr="d")) + ".csv",
        #     str(caltime),
        #     method="csv",
        # )
        # self.file.flush_buffer("01_Data/04_Time/"+ str(self.file.timestr(timstr="d")) + ".csv", method="csv")

    def _engine_command(self, enginID):
        if enginID == 0:

            def change_gear_status(new_status):
                self.left_gear_status = new_status

            with self.left_lock:
                stop_event = self.left_stop_event
                curvoltval = self.left_curvoltval
                current_gear_status = self.left_gear_status
                lock = self.left_lock
            send_acc = "LPS_L_DEC"
            send_dec = "LPS_L_ACC"
            send_forward = "LPS_L_Forward"
            send_neutral = "LPS_L_Neutral"
            send_reverse = "LPS_L_Reverse"
            real_vol = int(self.rawdata["LPS_L_vol"]) * 0.001
        elif enginID == 1:

            def change_gear_status(new_status):
                self.right_gear_status = new_status

            with self.right_lock:
                stop_event = self.right_stop_event
                curvoltval = self.right_curvoltval
                current_gear_status = self.right_gear_status
                lock = self.right_lock
            send_acc = "LPS_R_DEC"
            send_dec = "LPS_R_ACC"
            send_forward = "LPS_R_Forward"
            send_neutral = "LPS_R_Neutral"
            send_reverse = "LPS_R_Reverse"
            real_vol = int(self.rawdata["LPS_R_vol"]) * 0.001
        else:
            print(f"[動作] enginID : {enginID} 錯誤ID")
            return

        return {
            "stop_event": stop_event,
            "curvoltval": curvoltval,
            "current_gear_status": current_gear_status,
            "lock": lock,
            "send_acc": send_acc,
            "send_dec": send_dec,
            "send_forward": send_forward,
            "send_neutral": send_neutral,
            "send_reverse": send_reverse,
            "real_vol": real_vol,
            "change_gear_status": change_gear_status,
        }

    def _gear_status(self, decision):
        # 根據決策值確定要執行的俥指令狀態。
        if decision >= 0.6:
            return "forward"
        elif decision <= -1.46:
            return "reverse"
        else:
            return "neutral"

    def _gear_change(self, enginID, current_gear_status, new_gear_status, real_vol):
        """
        只有當俥狀態發生變化時執行指令
        """
        if new_gear_status == current_gear_status:
            # 沒有變化，不執行任何操作
            return False

        # 中立位置的切換方法映射
        gear_change_methods = {
            ("forward", "reverse"): [self._switch_to_neutral, self._switch_to_reverse],
            ("reverse", "forward"): [self._switch_to_neutral, self._switch_to_forward],
            ("neutral", "forward"): [self._switch_to_forward],
            ("neutral", "reverse"): [self._switch_to_reverse],
            ("forward", "neutral"): [self._switch_to_neutral],
            ("reverse", "neutral"): [self._switch_to_neutral],
        }

        # 延遲時間映射表
        delay_times = {
            ("forward", "reverse"): [1.0, 0.5],
            ("reverse", "forward"): [1.0, 0.5],
            ("neutral", "forward"): [0.50],
            ("neutral", "reverse"): [0.50],
            ("forward", "neutral"): [0.50],
            ("reverse", "neutral"): [0.50],
        }

        # 尋找對應的切換方法
        change_sequence = gear_change_methods.get(
            (current_gear_status, new_gear_status)
        )
        delay_sequence = delay_times.get((current_gear_status, new_gear_status))

        if change_sequence is None:
            print("---俥位名稱錯誤")
            return False

        # 執行變速操作
        # 測試#延遲時間
        # start = time.time()
        for change_method, delay in zip(change_sequence, delay_sequence):
            if not change_method(enginID, real_vol, delay):
                # 如果任何一次變速操作失敗，則中止並返回 False
                return False
        # end = time.time()
        # print("打檔完成時間:",end-start,"current_gear_status:",current_gear_status, "new_gear_status:",new_gear_status)
        # 所有變速操作成功後，更新變速狀態
        engine_command = self._engine_command(enginID)
        with engine_command["lock"]:
            engine_command["change_gear_status"](new_gear_status)
        return True

    def _switch_to_neutral(self, enginID, real_vol, delay):
        if self.gear_ser is not None:
            if enginID == 0:
                # time.sleep(0.08)
                self.send_board_command("LPS_L_Neutral")
            else:
                # time.sleep(0.08)
                self.send_board_command("LPS_R_Neutral")
            time.sleep(delay)
            # 等待 real_vol 更新到空檔電壓範圍
            if self._wait_for_real_vol(enginID, 2.65, 2.75):
                new_engine_command = self._engine_command(enginID)
                self.Adjustment(enginID=enginID, adjVal=new_engine_command["real_vol"])
                print(f"enginID:{enginID},只有當俥狀態發生變化時才執行指令", "純空檔")
                return True
            else:
                self.Adjustment(enginID=enginID, adjVal=real_vol)
                print(f"enginID:{enginID},純空檔尚未打好")
                return False
        else:
            # 測試#延遲時間
            time.sleep(delay)
            self.Adjustment(enginID=enginID, adjVal=2.71)
            print(f"enginID:{enginID},---純空檔")
            return True

    def _switch_to_forward(self, enginID, real_vol, delay):
        if self.gear_ser is not None:
            new_engine_command = self._engine_command(enginID)
            # 確保清空所有舊指令
            self._clear_command_queue()
            if enginID == 0:
                # time.sleep(0.08)
                self.send_board_command("LPS_L_Forward")
            else:
                # time.sleep(0.08)
                self.send_board_command("LPS_R_Forward")
            time.sleep(delay)
            if enginID == 0:
                # time.sleep(0.08)
                self.send_board_command("LPS_L_Forward")
            else:
                # time.sleep(0.08)
                self.send_board_command("LPS_R_Forward")
            if self._wait_for_real_vol(enginID, 2.0, 2.3):
                self.Adjustment(enginID=enginID, adjVal=new_engine_command["real_vol"])
                print(f"enginID:{enginID},只有當俥狀態發生變化時才執行指令", "純進檔")
                return True
            else:
                if enginID == 0:
                    # time.sleep(0.08)
                    self.send_board_command("LPS_L_Forward")
                else:
                    # time.sleep(0.08)
                    self.send_board_command("LPS_R_Forward")
                self.Adjustment(enginID=enginID, adjVal=new_engine_command["real_vol"])
                print(f"enginID:{enginID},純進檔尚未打好，直接再送一次")
                return False
        else:
            # 測試#延遲時間
            time.sleep(delay)
            self.Adjustment(enginID=enginID, adjVal=2.19)
            print(f"enginID:{enginID},---純進檔")
            return True

    def _switch_to_reverse(self, enginID, real_vol, delay):
        if self.gear_ser is not None:
            new_engine_command = self._engine_command(enginID)
            # 確保清空所有舊指令
            self._clear_command_queue()
            if enginID == 0:
                # time.sleep(0.08)
                self.send_board_command("LPS_L_Reverse")
            else:
                # time.sleep(0.08)
                self.send_board_command("LPS_R_Reverse")
            time.sleep(delay)
            if enginID == 0:
                # time.sleep(0.08)
                self.send_board_command("LPS_L_Reverse")
            else:
                # time.sleep(0.08)
                self.send_board_command("LPS_R_Reverse")
            if self._wait_for_real_vol(enginID, 3.2, 3.3):
                self.Adjustment(enginID=enginID, adjVal=new_engine_command["real_vol"])
                print(f"enginID:{enginID},只有當俥狀態發生變化時才執行指令", "純退檔")
                return True
            else:
                if enginID == 0:
                    # time.sleep(0.08)
                    self.send_board_command("LPS_L_Reverse")
                else:
                    # time.sleep(0.08)
                    self.send_board_command("LPS_R_Reverse")
                self.Adjustment(enginID=enginID, adjVal=new_engine_command["real_vol"])
                print(f"enginID:{enginID},純退檔尚未打好")
                return False
        else:
            # 測試#延遲時間
            time.sleep(delay)
            self.Adjustment(enginID=enginID, adjVal=3.24)
            print(f"enginID:{enginID},---純退檔")
            return True

    def _calculate_voltage_steps(self, decision, curvoltval, range):
        # 計算目標電壓值計算需要的步驟變化
        target_voltval = (5 - decision) / 2
        step_change = round(abs(target_voltval - curvoltval) / range)
        print(
            f"需要的步驟變化: {step_change}, 當前電壓: {curvoltval}V, 目標電壓: {target_voltval}V"
        )
        return step_change

    def _judge_send_command(self, decision, curvoltval, engine_command, range):
        # 檢查 range 的值是否為允許的範圍
        target_voltval = (5 - decision) / 2

        if range == 0.01:
            acc_command = engine_command["send_acc"]
            dec_command = engine_command["send_dec"]
        elif range == 0.05:
            dec_command = (
                "LPS_L_ACC_Five"
                if "LPS_L" in engine_command["send_acc"]
                else "LPS_R_ACC_Five"
            )
            acc_command = (
                "LPS_L_DEC_Five"
                if "LPS_L" in engine_command["send_dec"]
                else "LPS_R_DEC_Five"
            )
        elif range == 0.1:
            dec_command = (
                "LPS_L_ACC_Ten"
                if "LPS_L" in engine_command["send_acc"]
                else "LPS_R_ACC_Ten"
            )
            acc_command = (
                "LPS_L_DEC_Ten"
                if "LPS_L" in engine_command["send_dec"]
                else "LPS_R_DEC_Ten"
            )
        else:
            raise ValueError(f"無效的 range 值: {range}")

        if target_voltval > curvoltval:
            # 增加電壓
            return acc_command, range
        else:
            # 減少電壓
            return dec_command, -range

    def _adjust_speed(
        self, step_count, send_command, enginID, volt_change, stop_event, decision
    ):
        # 測試#延遲時間

        target_voltval = (5 - decision) / 2
        for _ in range(step_count):
            if stop_event.is_set():
                self._clear_command_queue()
                print(f"enginID:{enginID},俥檔被中斷")
                return False
            if enginID == 0:
                with self.left_lock:
                    self.left_curvoltval += volt_change
                    current_volt = round(self.left_curvoltval, 3)
                    # print(f"{enginID},目前電壓值{current_volt}")
            else:
                with self.right_lock:
                    self.right_curvoltval += volt_change
                    current_volt = round(self.right_curvoltval, 3)
                    # print(f"---{enginID},目前電壓值{current_volt}")
            # 測試#延遲時間
            # time.sleep(0.3)
            # 記錄電壓變化
            result = f"{enginID},{current_volt},{send_command},{decision}"
            self.file.writefile(
                "01_Data/03_LeverSys/" + str(self.file.timestr(timstr="d")) + ".csv",
                str(result),
                method="csv",
            )

            # 執行指令
            if self.gear_ser is not None:
                # print(f"4444444enginID:{enginID},當前電壓: {self._engine_command(enginID)["real_vol"]}, 目標電壓: {target_voltval}V")
                # self.send_board_command(send_command)
                # if self._engine_command(enginID)["real_vol"] == target_voltval:
                #     print("444444444444444444達到目標電壓不再傳送step指令")
                #     break
                # print(
                #     "444444444444444444達到目標電壓不再傳送step指令",
                #     self._engine_command(enginID)["real_vol"],
                #     target_voltval,
                # )
                self.send_board_command(send_command)
                time.sleep(0.8)
                # 延遲時間

        # self._clear_command_queue()

        # print("動作完成時間",end-start,"step_count:" ,step_count, "send_command:",send_command,"enginID:" ,enginID,"volt_change:", volt_change,"decision:" ,decision)
        # if self.gear_ser is not None:
        # 如果直沒有被中斷的話就校正
        return True

    def _wait_for_real_vol(self, enginID, expected_min, expected_max, timeout=1.0):
        # 測試#延遲時間
        # 等待 real_vol 更新到指定範圍
        start_time = time.time()
        while time.time() - start_time < timeout:
            real_vol = (
                self.rawdata["LPS_L_vol"] if enginID == 0 else self.rawdata["LPS_R_vol"]
            )
            real_vol = float(real_vol) * 0.001
            if expected_min <= real_vol <= expected_max:
                return True
            time.sleep(0.01)  # 等待 10ms 重新檢查
        return False

    def shutdown(self):
        self.left_executor.shutdown(wait=True)
        self.right_executor.shutdown(wait=True)

    def call(self):
        # 要等空俥才可以叫站
        if self.gear_ser is not None:
            if self.rawdata["ACTIVE_LED"] == "0":
                self.neutral()
                time.sleep(0.5)
                self.send_board_command("STA_SEL_LONG_PRESS")
                time.sleep(2)
                return True
                # print("叫站成功")
            else:
                return False
        else:
            return False

    def neutral(self):
        # 要等空俥才可以叫站
        if self.gear_ser is not None:
            self._clear_command_queue()  # 確保清空所有舊指令
            self.send_board_command("LPS_L_Neutral")
            # 測試#延遲時間
            # time.sleep(0.3)
            self.send_board_command("LPS_R_Neutral")
            # 測試#延遲時間
            # time.sleep(0.3)
            self.Adjustment(enginID=0, adjVal=2.71)
            self.Adjustment(enginID=1, adjVal=2.71)
            # print("兩俥進空檔")


# 使用範例
if __name__ == "__main__":
    # 開啟串口
    gear_system = LeverSys(port="COM11")
    # 連接
    # gear_system.open()
    # time.sleep(1)
    # 叫站
    # gear_system.call()
    # 接收值
    received_data = gear_system.receive_data()
    # 校準
    gear_system.Adjustment(enginID=0, adjVal=2.71)
    gear_system.Adjustment(enginID=1, adjVal=2.71)
    # 控制引擎速度
    gear_system.controlGear(enginID=1, decision=1.1, range=0.01)
    gear_system.controlGear(enginID=1, decision=3, range=0.1)
