from flask import Flask, request, jsonify, render_template
from threading import Thread, Lock
import time
from controlsys import ControlSys


# 初始化 Flask 應用
app = Flask(__name__)

# 共享變數
last_command = {'Command': 0, 'Speed': -0.42,'Range':0.01}
last_command_time = time.time()
last_command_direction_executed = False

lock = Lock()

# 初始化 ControlSys 實例
ControlSys = ControlSys(gear_system_port="COM11", rudder_systemEnZero_port='COM12', rudder_systemEnOne_port='COM13')
# 校準
ControlSys.gear_system.Adjustment(enginID=0, adjVal=2.71)
ControlSys.gear_system.Adjustment(enginID=1, adjVal=2.71)
ControlSys.rudder_systemEnZero.Adjustment(0)
ControlSys.rudder_systemEnOne.Adjustment(0)

#整理
def execute_command(command_data):
    """執行控制指令的核心函數，根據命令類型進行對應處理"""
    command = command_data.get('Command', 0)
    global last_command_direction_executed
    if command == 666:
        last_command_direction_executed = command
        # 精密控制模式
        msg = ControlSys.decision(
            Command=command,
            Left_Speed=command_data.get('Left_Speed', -0.42),
            Left_Rudder=command_data.get('Left_Rudder', 0),
            Right_Speed=command_data.get('Right_Speed', -0.42),
            Right_Rudder=command_data.get('Right_Rudder', 0),
            Range = command_data.get('Range', 0.01),
        )
        return msg
    elif command >= 900:
        # 高優先指令處理
        # global last_command_direction_executed
        if command != last_command_direction_executed:
            msg=ControlSys.decision(Command=command)
            last_command_direction_executed = command
            # print("7777777777",last_command_direction_executed)
            return msg
        else:
            msg = ControlSys.decision(Command=0)
            # print("8888888888888888888888888888888888")
            return msg
    elif command==701:
        last_command_direction_executed = command
        #speed還沒條
        # print("6666666666666666",command_data)
        msg=ControlSys.decision(Command=command, Current_heading=command_data.get('Current_heading', 0),Range=command_data.get('Range', 0.01),Speed=command_data['Speed'] )
    else:
        # 常規指令處理
        last_command_direction_executed = command
        msg=ControlSys.decision(Command=command, Speed=command_data.get('Speed', -0.42),Range=command_data.get('Range', 0.01))
        return msg

#----------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def status():
    with lock:
        current_status = {
            'Command': last_command['Command'],
            'Speed': last_command.get('Speed', 666),
            'Voltage': {
                'status':ControlSys.gear_system.connect(),
                'Engine0': ControlSys.gear_system.left_curvoltval,
                'Engine1': ControlSys.gear_system.right_curvoltval,
                'rawdata':ControlSys.gear_system.rawdata,
                'rawdata0':ControlSys.gear_system.rawdata0,
                'rawdata1':ControlSys.gear_system.rawdata1,
                'Engine0_left_gear_status':ControlSys.gear_system.left_gear_status,
                'Engine1_right_gear_status':ControlSys.gear_system.right_gear_status,
            },
            'RudderAngle': {
                'status0':ControlSys.rudder_systemEnZero.connect(),
                'status1':ControlSys.rudder_systemEnOne.connect(),
                'Engine0': ControlSys.rudder_systemEnZero.currudder,
                'Engine1': ControlSys.rudder_systemEnOne.currudder,
                'rawdata0':ControlSys.rudder_systemEnZero.rawdata,
                'rawdata1':ControlSys.rudder_systemEnOne.rawdata
            },
        }
    return jsonify(current_status)

@app.route('/control', methods=['POST'])
def control():
    #控制指令選擇
    global last_command, last_command_time

    data = request.get_json()
    if not data or 'Command' not in data:
        return jsonify({'status': 'error', 'message': '無效的輸入'}), 400

    with lock:
        command = data['Command']

        # 根據命令類型更新 last_command
        if command == 666:
            last_command = {
                'Command': command,
                'Left_Speed': data.get('Left_Speed', -0.42),
                'Left_Rudder': data.get('Left_Rudder', 0),
                'Right_Speed': data.get('Right_Speed', -0.42),
                'Right_Rudder': data.get('Right_Rudder', 0),
                'Range': data.get('Range', 0.01)
            }
        elif command >= 900:
            last_command = {'Command': command}
        elif command==701:
            last_command = {
                'Command': command,
                'Current_heading':data.get('Current_heading', 0),
                'Range':data.get('Range', 0.01),
                'Speed':data.get('Speed', -0.42)
            }
        else:
            last_command = {
                'Command': command,
                'Speed': data.get('Speed', -0.42),
                'Range': data.get('Range', 0.01)
            }

        # 執行指令
        msg=execute_command(last_command)
        last_command_time = time.time()

        return jsonify({**last_command, 'status': 200,'msg':msg})

def control_loop():
    #持續控制指令的執行迴圈
    global last_command_direction_executed, last_command_time

    while True:
        with lock:
            elapsed_time = time.time() - last_command_time

            if elapsed_time > 60:
                # 超時重置指令
                ControlSys.decision(Command=0)
            else:
                # 執行最新指令
                if last_command['Command'] == 701:
                    # print("555555555555",last_command)
                    last_command['Current_heading'] = ControlSys.rudder_systemEnZero.rawdata['Heading']

                    # last_command['current_heading'] = round(random.uniform(100.9, 110.5), 2)
                    # print("555555555555","有更新current_heading",last_command)
                else:
                    ControlSys.autoHeading.last_heading = None
                execute_command(last_command)

        time.sleep(3)  # 根據需要調整睡眠時間

@app.route('/calibrate', methods=['POST'])
def calibrate():
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': '無效的輸入'}), 400

    # 獲取校準值
    gear_adj_engine0 = data.get('gear_adj_engine0')
    gear_adj_engine1 = data.get('gear_adj_engine1')
    rudder_adj_engine0 = data.get('rudder_adj_engine0')
    rudder_adj_engine1 = data.get('rudder_adj_engine1')

    # 校驗輸入值
    if gear_adj_engine0 is None or gear_adj_engine1 is None or rudder_adj_engine0 is None or rudder_adj_engine1 is None:
        return jsonify({'status': 'error', 'message': '缺少校準值'}), 400

    # 應用校準值
    with lock:
        ControlSys.gear_system.Adjustment(enginID=0, adjVal=gear_adj_engine0)
        ControlSys.gear_system.Adjustment(enginID=1, adjVal=gear_adj_engine1)
        ControlSys.rudder_systemEnZero.Adjustment(rudder_adj_engine0)
        ControlSys.rudder_systemEnOne.Adjustment(rudder_adj_engine1)

    return jsonify({'status': '校準完成'})
if __name__ == '__main__':
    # # 在單獨的執行緒中啟動控制迴圈
    # control_thread = Thread(target=control_loop)
    # control_thread.daemon = True
    # control_thread.start()

    # # 在單獨的執行緒中啟動數據接收迴圈
    # data_receive_thread = Thread(target=data_receive_loop)
    # data_receive_thread.daemon = True
    # data_receive_thread.start()

    # 定義需要運行的函數
    threads = [
        Thread(target=control_loop, daemon=True),
        # Thread(target=data_receive_loop, daemon=True)
    ]
    
    # 啟動所有線程
    for thread in threads:
        thread.start()
    # 運行 Flask 應用
    app.run(host='0.0.0.0', port=5899)
