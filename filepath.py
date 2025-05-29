import os
import shutil
import json
import time
import csv
from threading import Lock

class fileControl:
    def __init__(self):
        self.buffers = {}  # 每個檔案有自己的緩衝區
        self.buffer_size = 10  # 緩衝幾筆儲存一次資料
        self.file_lock = Lock()  # 增加鎖
        self.flush_interval = 1  # 批量寫入的間隔時間（秒）
        self.last_flush_times = {}  # 記錄每個檔案的上次寫入時間
        self.open_files = {}  # 儲存已開啟的檔案物件，方便關閉

    # 建立資料夾
    def addfolder(self, add_folder, clean=False):
        if isinstance(add_folder, str):
            if clean and os.path.exists(add_folder):
                shutil.rmtree(add_folder)  
            os.makedirs(add_folder, exist_ok=True)
        elif isinstance(add_folder, list):
            for add in add_folder:
                if clean and os.path.exists(add):
                    shutil.rmtree(add)  
                os.makedirs(add, exist_ok=True)  

    # 寫入資料
    def writefile(self, filename, content, method="a"):
        with self.file_lock:
            if filename not in self.buffers:
                self.buffers[filename] = []  # 為每個檔案建立獨立緩衝區
                self.last_flush_times[filename] = time.time()  # 設定初始時間
            
            self.buffers[filename].append(str(content))
            current_time = time.time()

            # 檢查是否達到批量寫入條件
            if len(self.buffers[filename]) >= self.buffer_size or (current_time - self.last_flush_times[filename] >= self.flush_interval):
                self.flush_buffer(filename, method)
                self.last_flush_times[filename] = current_time  # 更新上次寫入時間

    def flush_buffer(self, filename, method="a"):
        if filename not in self.buffers or not self.buffers[filename]:
            return  # 沒有緩衝資料則跳過

        name = filename.split("/")
        filepath = filename[:-len(name[-1])]
        self.addfolder(filepath)

        with open(filename, "a" if method == "csv" else method, encoding='utf-8', newline='\n') as f:
            if method == "csv":
                writer = csv.writer(f)
                for item in self.buffers[filename]:
                    writer.writerow([time.time(), item])
            else:
                f.write(''.join(self.buffers[filename]))

        self.buffers[filename].clear()  # 清空該檔案的緩衝區
        self.open_files[filename] = f  # 儲存開啟的檔案以便關閉

    # 關閉所有開啟的檔案，確保緩衝區寫入
    def close(self):
        with self.file_lock:
            for filename in list(self.buffers.keys()):
                self.flush_buffer(filename)  # 確保所有檔案的緩衝都寫入

            for f in self.open_files.values():
                f.close()
            self.open_files.clear()
            self.buffers.clear()

    # 根路徑    
    def rootpath(self):
        return os.getcwd()
    
    # 此路徑檔案名稱        
    def filelist(self, filename):
        try:
            return os.listdir('./'+filename)
        except:
            return []
    
    # 檔案路徑    
    def filepath(self, filename):
        return os.path.join(self.rootpath(), filename)
    
    # 時間文字格式
    def timestr(self, timstr="s"):
        now = time.localtime(time.time())
        if timstr == "s":
            times = time.strftime("%Y_%m_%d_%H_%M_%S", now)
        elif timstr == "m":
            times = time.strftime("%Y_%m_%d_%H_%M", now)
        elif timstr == "d":
            times = time.strftime("%Y_%m_%d", now)
        else:
            times = time.strftime("[Wrong]%Y_%m_%d_%H_%M_%S", now)
        return times
    
    # 回補檔案並移檔
    def backdata(self, startfilename, endfilename):
        result = []
        filelist = self.filelist(startfilename)
        logfilename = "01_Nodata/05_backup.txt"
        if filelist:
            for fil in filelist:
                file_path = self.filepath(startfilename + fil)
                try:        
                    with open(file_path, 'r') as json_file:
                        json_content = json.loads(json_file)
                        result.append(json_content)
                except json.decoder.JSONDecodeError:
                    self.writefile(logfilename, f"[{self.timestr()}] [Nodata] {file_path} file error must be JSON\n")
                except Exception as e:
                    self.writefile(logfilename, f"[{self.timestr()}] [Nodata] {file_path} {e}\n")
        return result

    def movefile(self, file1, file2):
        try:
            self.addfolder(file2)
            shutil.move(file1, file2)
        except:
            print("[movefile] 移動檔案時有重複檔名之檔案")

    def readCsvfile(self, path, filename):
        result = []
        with open(path + filename, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                result.append([float(row[0]), float(row[1])])
        return {filename: result}
        
    # 地圖座標讀取    
    def read_polygon_vertices(self, file_name):
        vertices = []
        with open(file_name, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                vertices.append([float(row[0]), float(row[1])])
        return vertices
        
    def readJsonfile(self, path, filename):
        with open(path + filename, mode='r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    
# 使用範例
if __name__ == "__main__":
    file = fileControl()
    result = "123"
    #我有寫緩衝，所以如果資料量太少要加flush_buffer才可以儲存
    file.writefile("01_Data/00_Test/"+ str(file.timestr(timstr="d")) + ".csv", str(result), method="csv")
    # file.flush_buffer("01_Data/00_Test/"+ str(file.timestr(timstr="d")) + ".csv", method="csv")
    file.writefile("01_Data/00_Test/55688.csv", str(456), method="csv")
    # file.flush_buffer("01_Data/00_Test/55688.csv", method="csv")
    print(file.buffers)
    
