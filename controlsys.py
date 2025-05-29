from leverboard import LeverSys
from rudderboard import RudderSys
import time
import threading
from boatcontroller import Cal_Rudder_Engine 
import math
from filepath import fileControl
class ControlSys():
    def __init__(self, gear_system_port="COM11", rudder_systemEnZero_port='COM12', rudder_systemEnOne_port='COM13'):
        self.gear_system = LeverSys(port=gear_system_port)
        self.rudder_systemEnZero = RudderSys(port=rudder_systemEnZero_port,enginID="0")
        self.rudder_systemEnOne = RudderSys(port=rudder_systemEnOne_port,enginID="1")
        self.autoHeading = Cal_Rudder_Engine()

        # # 啟動檢查指令的執行緒
        self.last_command_time = time.time()
        self.current_command = None
        self.file = fileControl()
        # 指令映射：指令代碼對應處理方法
        self.command_map = {
            1: self.Forward,
            2: self.TopRight,
            3: self.Right,
            4: self.LowerRight,
            -1: self.Backward,
            -2: self.TopLeft,
            -3: self.Left,
            -4: self.LowerLeft,
            5: self.Translation_TopRight,
            -5: self.Translation_TopLeft,
            6: self.Translation_Right,
            -6: self.Translation_Left,
            7: self.Translation_LowerRight,
            -7: self.Translation_LowerLeft,
            8: self.Rotate_Clockwise,
            -8: self.Rotate_CounterClockwise,
            -9:self.Backward_LowerLeft,
            -10:self.Backward_LowerRight,
            666:self.Finecontrol,
            701:self.AutoHeading,
            0: self.Stop,
            900: self.connected,
            901: self.Callstation,
            999: self.close,
        }

    def decision(self, Command=0, **kwargs):
        # print(f"[DEBUG] 嘗試執行指令: {Command}")

        # if self.gear_system is None:
        #     print("[ERROR] gear_system 是 None，可能被垃圾回收！")
        #     return

        # if self.gear_system.left_executor is None or self.gear_system.right_executor is None:
        #     print("[ERROR] gear_system 的執行緒池已經被回收")
        #     return

        # if self.gear_system.left_executor._shutdown or self.gear_system.right_executor._shutdown:
        #     print("[ERROR] gear_system 的執行緒池已關閉，無法提交任務")
        #     return

        # print("[DEBUG] gear_system 和 rudder_system 仍然存活，執行指令")
        self.current_command = Command
        self.last_command_time = time.time()

        # 根據 Command 呼叫相應的控制方法
        if Command in self.command_map:
            msg=self.command_map[Command](**kwargs)
            return msg
        else:
            msg = "無效指令"
            print(msg)
            return msg
           
    def connected(self, **kwargs):
        Isconnect1=self.rudder_systemEnZero.open()
        Isconnect2=self.rudder_systemEnOne.open()
        Isconnect3=self.gear_system.open()

        if Isconnect1 and Isconnect2 and Isconnect3:
            msg = "連接成功"
            print(msg)
            return msg            
        else:
            msg = "連接失敗"
            print(msg)
            return msg  

    def close(self, **kwargs):
        self.rudder_systemEnZero.rudder_ser = None   
        self.rudder_systemEnOne.rudder_ser = None   
        self.gear_system.gear_ser = None 
        self.gear_system.rawdata = {'NEUTRAL_LED': '0', 'ACTIVE_LED': '0', 'SYNC_LED': '0','LPS_L_vol': '0', 'LPS_R_vol': '0',}
        msg = "斷開連結"
        print(msg)
        return msg
        

    def _control_gear(self, adjusted_gear_left, adjusted_gear_right,range):
        # 控制兩個發動機的傳動系統，並限制速度在最小最大範圍內

        # 設定進俥與退俥的最小與最大值
        if -1.46<adjusted_gear_left<0.6: #空俥
            adjusted_gear_left = -0.42
        elif adjusted_gear_left > 0:  # 進俥
            adjusted_gear_left = self._clamp(adjusted_gear_left, 0.62, 5)  # 進俥電壓最小值 0.62
        else :  # 退俥
            adjusted_gear_left = self._clamp(adjusted_gear_left, -4, -1.48)  # 退俥電壓最小值 -1.46

        if -1.46<adjusted_gear_right<0.6:#空俥
            adjusted_gear_right=-0.42
        elif adjusted_gear_right > 0:  # 進俥
            adjusted_gear_right = self._clamp(adjusted_gear_right, 0.62, 5)  # 進俥電壓最小值 0.62
        else:  # 退俥
            adjusted_gear_right = self._clamp(adjusted_gear_right, -4, -1.48)  # 退俥電壓最小值 -1.46

        range = self._calrange(range)

        # 控制左、右發動機
        print("控制左、右發動機",adjusted_gear_left,adjusted_gear_right)
        self.gear_system.controlGear(enginID=0, decision=adjusted_gear_left,range=range)
        #測試#延遲時間  
        time.sleep(0.1)
        self.gear_system.controlGear(enginID=1, decision=adjusted_gear_right,range=range)
        time.sleep(0.1)
                # 控制左、右發動機
        # print("只控制左引擎",adjusted_gear_left,adjusted_gear_right)
        # self.gear_system.controlGear(enginID=0, decision=adjusted_gear_right,range=range)
        # time.sleep(0.1)

    def _control_rudder(self, left_rudder, right_rudder):
        left_rudder = self._clamp(left_rudder, -30, 30)
        right_rudder = self._clamp(right_rudder, -30, 30)
        self.rudder_systemEnZero.controlRudder(decision=left_rudder)
        self.rudder_systemEnOne.controlRudder(decision=right_rudder)

    def _clamp(self, value, min_value, max_value):
        # 確保值在給定的範圍內
        return max(min(value, max_value), min_value)
    
    def _calrange(self,value):
        # 加速度許可的範圍值
        allowed_ranges = [0.01, 0.05, 0.1]  
        if value in allowed_ranges:
            return value
        else:
            print(f"警告: 無效的 range 值 {value}，已重設為預設值 0.01")
            return 0.01

    
    
    def Forward(self, **kwargs):
        # 前進
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        forwordval = Gear
        self._control_gear(forwordval, forwordval,Range)
        self._control_rudder(0, 0)
        msg = "前進"
        print(msg)
        return msg
        

    def Backward(self,**kwargs):
        # 後退
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(backval, backval,Range)
        self._control_rudder(0, 0)
        msg = "後退"
        print(msg)
        return msg

    def TopRight(self, **kwargs):
        # 右上
        Gear = kwargs.get('Speed', -0.42)
        forwordval = Gear
        Range = kwargs.get('Range', 0.01)
        # backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(forwordval, forwordval,Range)
        self._control_rudder(0, 10)
        msg = "右上"
        print(msg)
        return msg
    def Right(self, **kwargs):
        # 右邊 
        Gear = kwargs.get('Speed', -0.42)
        forwordval = Gear
        Range = kwargs.get('Range', 0.01)
        # backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(forwordval, forwordval,Range)
        self._control_rudder(20, 20)
        msg = "右邊"
        print(msg)
        return msg
    def LowerRight(self, **kwargs):
        # 右下
        Gear = kwargs.get('Speed', -0.42)
        forwordval = Gear
        Range = kwargs.get('Range', 0.01)
        # backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(forwordval, forwordval,Range)
        self._control_rudder(25, 25)  
        msg = "右下"
        print(msg)
        return msg
    def TopLeft(self, **kwargs):
        # 左上
        Gear = kwargs.get('Speed', -0.42)
        forwordval = Gear
        Range = kwargs.get('Range', 0.01)
        # backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(forwordval, forwordval,Range)
        self._control_rudder(-10, 0)
        msg = "左上"
        print(msg)
        return msg
    def Left(self, **kwargs):
        # 左邊
        Gear = kwargs.get('Speed', -0.42)
        forwordval = Gear
        Range = kwargs.get('Range', 0.01)
        # backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(forwordval, forwordval,Range)
        self._control_rudder(-20, -20)
        msg = "左邊"
        print(msg)
        return msg
    def LowerLeft(self, **kwargs):
        # 左下
        Gear = kwargs.get('Speed', -0.42)
        forwordval = Gear
        Range = kwargs.get('Range', 0.01)
        # backval=-1.98 - 1* (Gear - 1)
        self._control_gear(forwordval, forwordval,Range)
        self._control_rudder(-25, -25)
        msg = "左下"
        print(msg)
        return msg
    def Stop(self, **kwargs):
        # 空俥
        # self._control_gear(-0.42, -0.42)
        self.Neutral()
        self._control_rudder(0, 0)
        msg = "空俥"
        print(msg)
        return msg
    def Rotate_Clockwise(self, **kwargs):
        # 順時針
        Gear = kwargs.get('Speed', -0.42)
        ratio = 1.2
        forwordval = Gear
        backval=-1.98 - 1* (Gear - 1)
        Range = kwargs.get('Range', 0.01)
        self._control_gear(forwordval, backval,Range)
        self._control_rudder(20, -20)
        msg = "順時針"
        print(msg)
        return msg
    def Rotate_CounterClockwise(self, **kwargs):
        # 逆時針
        Gear = kwargs.get('Speed', -0.42)
        ratio = 1.2
        forwordval = Gear
        Range = kwargs.get('Range', 0.01)
        backval=-1.98 - 1* (Gear - 1)
        self._control_gear(backval, forwordval,Range)
        self._control_rudder(20, -20)
        msg = "逆時針"
        print(msg)
        return msg
    def Translation_TopRight(self, **kwargs):
        # 右上平移
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        ratio = 1.25
        forwordval = ratio * Gear
        backval=-1.98 - (Gear - 1)
        self._control_gear(forwordval,backval,Range)
        self._control_rudder(-20, 30)
        msg = "右上平移"
        print(msg)
        return msg
    def Translation_Right(self, **kwargs):
        # 右平移
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        ratio = 1.4
        forwordval = Gear
        backval=-1.98 - ratio * (Gear - 1)
        self._control_gear(forwordval,backval,Range)
        self._control_rudder(-25, 25)
        msg = "右平移"
        print(msg)
        return msg
    def Translation_LowerRight(self, **kwargs):
        # 右下平移
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        ratio = 1.8
        forwordval = Gear
        backval=-1.98 - ratio * (Gear - 1)
        self._control_gear(forwordval,backval,Range)
        self._control_rudder(-30, 30) 
        msg = "右下平移"
        print(msg)
        return msg
    def Translation_TopLeft(self, **kwargs):
        '''左上平移
        y(左  x(右)
        -1     1.25
        -1.1  1.38
        -1.2  1.5
        y = -0.8x'''
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        ratio = 1.25
        forwordval = ratio *Gear
        backval=-1.98 -  (Gear - 1)
        self._control_gear(backval,forwordval,Range)
        self._control_rudder(-30, 20)
        msg = "左上平移"
        print(msg)
        return msg
    def Translation_Left(self, **kwargs):
        '''左平移
        y(左  x(右)
        -1     1
        -1.14  1.1
        -1.28  1.2

        y = -1.4x+0.4'''
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        ratio = 1.4
        forwordval = Gear
        backval=-1.98 - ratio * (Gear - 1)
        self._control_gear(backval,forwordval,Range)
        self._control_rudder(-25, 25)
        msg = "左平移"
        print(msg)
        return msg
    def Translation_LowerLeft(self, **kwargs):
        '''左下平移
        y(左  x(右)
        -1     1
        -1.18  1.1
        -1.36  1.2

        y = -1.8x+0.8'''

        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        ratio = 1.8
        forwordval = Gear
        backval=-1.98 - ratio * (Gear - 1)
        self._control_gear(backval,forwordval,Range)
        self._control_rudder(-30, 30)
        msg = "左下平移"
        print(msg)
        return msg
    
    def Backward_LowerLeft(self,**kwargs):
        # 左下後退
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(backval, backval,Range)
        self._control_rudder(-25, -25)
        msg = "左下後退"
        print(msg)
        return msg
    
    def Backward_LowerRight(self,**kwargs):
        # 右下後退
        Gear = kwargs.get('Speed', -0.42)
        Range = kwargs.get('Range', 0.01)
        backval=-1.98 - 1 * (Gear - 1)
        self._control_gear(backval, backval,Range)
        self._control_rudder(25, 25)
        msg = "右下後退"
        print(msg)
        return msg
    def Finecontrol(self, **kwargs):
        Left_Speed = kwargs.get('Left_Speed', -0.42)
        if Left_Speed is None:
            Left_Speed = -0.42
        Left_Rudder = kwargs.get('Left_Rudder', 0)
        Right_Speed = kwargs.get('Right_Speed', -0.42)
        if Right_Speed is None:
            Right_Speed = -0.42
        Right_Rudder = kwargs.get('Right_Rudder', 0)
        Range = kwargs.get('Range', 0.01)
        if Left_Speed < -0.42:
            Left_Speed = Left_Speed - 0.98
        if Right_Speed < -0.42:
            Right_Speed = Right_Speed - 0.98
        self._control_gear(Left_Speed, Right_Speed, Range)
        self._control_rudder(Left_Rudder, Right_Rudder)
        msg = "精密控制成功"
        print(msg)
        return msg
    
    def AutoHeading(self, **kwargs):

        # 取得當前航向
        # new_heading = kwargs.get('current_heading', 0)   # 目前船舶的航向 (度)
        # print("9999999999999999",kwargs)
        new_heading = float(kwargs['Current_heading'])
        engine_power = kwargs['Speed']
        range = kwargs['Range']
        # print("777777777777777",new_heading)
        if self.autoHeading.last_heading is None:
            self.autoHeading.last_heading = new_heading
            print("調整1次")
        else:
            print("不調整")
        # 計算偏航率 (Yaw Rate)
        yaw_rate = self.autoHeading.calculate_yaw_rate(new_heading)
        
        # 計算舵角
        rudder_angle, target_heading, yaw_error = self.autoHeading.RudderAngleCalculation(new_heading,self.autoHeading.last_heading, yaw_rate)
        print("909090909090","目標航向",self.autoHeading.last_heading,"當前heading",new_heading)
        caltime = f"{time.time()},{self.autoHeading.last_heading},{new_heading},{engine_power},{range},{rudder_angle},{yaw_error}"
        
        self.file.writefile("01_Data/05_AutoHeading/"+ str(self.file.timestr(timstr="d")) + ".csv", str(caltime),method="csv")
        # self.autoHeading.last_heading = new_heading
        self.autoHeading.last_time = time.time()
        # 計算引擎輸出（維持一定前進速度）
        
        # # 控制舵角
        self._control_rudder(rudder_angle, rudder_angle)  # 雙舵同步控制

        # # 控制發動機
        self._control_gear(engine_power, engine_power, range=range)
        msg = f"航向保持: 目標航向 {target_heading:.2f}° 偏航誤差 {yaw_error:.2f}° 舵角 {rudder_angle}° 引擎功率 {engine_power:.2f}"
        print(msg)
        return msg

    def Callstation(self, **kwargs):
        # 叫站
        try:
            systemEnZero_RudderFeedback=int(self.rudder_systemEnZero.rawdata['RudderFeedback'])
            systemEnOne_RudderFeedback=int(self.rudder_systemEnOne.rawdata['RudderFeedback'])
        except:
            print("叫站時，舵角值獲取錯誤，請檢查現在舵角資訊")
            systemEnZero_RudderFeedback=0
            systemEnOne_RudderFeedback=0    

        
        if systemEnZero_RudderFeedback != 0: 
            if systemEnZero_RudderFeedback >0:
                systemEnZero_RudderFeedback = systemEnZero_RudderFeedback + 1
            elif  systemEnZero_RudderFeedback<0:
                systemEnZero_RudderFeedback = systemEnZero_RudderFeedback - 1
            self.rudder_systemEnZero.Adjustment(adjVal=systemEnZero_RudderFeedback)
            time.sleep(0.03)

        if systemEnOne_RudderFeedback !=0:
            if systemEnOne_RudderFeedback >0:
                systemEnOne_RudderFeedback = systemEnOne_RudderFeedback + 1
            elif  systemEnOne_RudderFeedback<0:
                systemEnOne_RudderFeedback = systemEnOne_RudderFeedback - 1
            self.rudder_systemEnOne.Adjustment(adjVal=systemEnOne_RudderFeedback)
            
        Iscall=self.gear_system.call()
        if Iscall:
            msg = "叫站成功"
            print(msg)
            return msg
        else:
            msg = "叫站失敗"
            print(msg)
            return msg
    def Neutral(self):
        # 強制空俥
        self.gear_system.neutral()
        self.gear_system.controlGear(enginID=0, decision=-0.42)
        #測試#延遲時間
        time.sleep(0.08)
        self.gear_system.controlGear(enginID=1, decision=-0.42)
        # msg = "兩俥進空俥"
        # print(msg)
        # return msg        




if __name__ == "__main__":
    ControlSys=ControlSys(gear_system_port="COM11", rudder_systemEnZero_port='COM12', rudder_systemEnOne_port='COM13')
    #校準實際值
    ControlSys.gear_system.Adjustment(enginID=0,adjVal=2.71)
    ControlSys.gear_system.Adjustment(enginID=1,adjVal=2.71)
    ControlSys.rudder_systemEnZero.Adjustment(adjVal=0)
    ControlSys.rudder_systemEnOne.Adjustment(adjVal=0)
    # s = ControlSys.decision(Command=900)

    # ControlSys.decision(Command=901)
    # # 空俥
    # ControlSys.decision(Command=0)
    # # 前進
    # ControlSys.decision(Command=1,Speed=1.2)
    # time.sleep(0.3)
    # ControlSys.decision(Command=1,Speed=1.2)
    # # 後退
    # ControlSys.decision(Command=-1,Speed=1)
    # # 右上
    # ControlSys.decision(Command=2,Speed=1.2)
    # # 右轉
    # ControlSys.decision(Command=3,Speed=1.2)
    # # 右下
    # ControlSys.decision(Command=4,Speed=1.2)
    # # 左上
    # ControlSys.decision(Command=-2,Speed=1.2)
    # # 左轉
    # ControlSys.decision(Command=-3,Speed=1.2)
    # # 左下
    # ControlSys.decision(Command=-4,Speed=1.2)
    # # 右平移
    # ControlSys.decision(Command=5,Speed=1)
    # # 左平移
    # ControlSys.decision(Command=-5,Speed=1)
    # # 順時針
    # ControlSys.decision(Command=6,Speed=1)
    # 逆時針
    # ControlSys.decision(Command=-6,Speed=1)
    # # 四角測試
    # ControlSys.decision(Command=1,Speed=1)
    # ControlSys.decision(Command=5,Speed=1)
    # ControlSys.decision(Command=-1,Speed=-1)
    # ControlSys.decision(Command=-5,Speed=1)
    # # #精密控制
    # ControlSys.decision(Command=666,Left_Speed=1,Left_Rudder=10,Right_Speed=2,Right_Rudder=3)
    # ControlSys.decision(Command=666,Left_Speed=-1,Left_Rudder=-10,Right_Speed=1,Right_Rudder=-3)
    ControlSys.decision(Command=701)
