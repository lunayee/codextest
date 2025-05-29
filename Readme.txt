注意事項
1.如果已經叫站，又再叫一次，螢幕的轉速會閃爍，然後會無法進俥退俥，目前只能先一站叫回去再重新叫一次解
2.記得所有測試完，最後指令一定要回空檔，不然一站叫不回去
3.速度決策值盡量從1.2慢慢加上去，要加多少都可以最多到2.0，如果要一次上去第一次指令盡量不要超過1.5
4.可以隨時切換，發現有問題也可以直接空檔，不需等待
5.COM要記得更改
6.control :http://127.0.0.1:5899
7.戰情室:https://ks-api.stockinfo888.com/Marina/Ship/ship_list
  帳號：hao1
　密碼：haohao
8.進俥決策最高5，退俥決策最高4
9.舵角幅度最多+-25

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
            "LPS_R_Reverse": "右俥退檔"
        }
10.螺旋槳的資料 lexor 9571-158-15
刀片:3
直徑:15.75
音高(PITCH):15
旋轉:標準
材質:不銹鋼產品 
MPN:9571-158-15
產品UPC:824375031359
直徑尺寸 15-3/4
15 音高右旋轉
螺距15表示螺旋槳旋轉1次。船將向前移動 15 英吋

11.主程式為apimain.py
12.阿榮板子程式中，如果進空檔，會有1秒的時間指令不會被接收，完全空1秒
13.打包 pyinstaller --onefile --add-data "templates;templates"  apimain.py
