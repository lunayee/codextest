import requests
import time

url = "http://127.0.0.1:5899/status"

# 設定測試頻率 (間隔時間, 單位: 秒)
test_intervals = [0.0000000000000001]  # 測試 1 秒、0.5 秒、0.25 秒、0.1 秒、0.05 秒

for interval in test_intervals:
    print(f"\n🔹 測試頻率: 每 {interval} 秒發送一次請求")
    success_count = 0
    error_count = 0
    total_requests = 2000  # 每個頻率測試 20 次

    for i in range(total_requests):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                success_count += 1
            else:
                error_count += 1
                print(f"⚠️ API 回應錯誤碼: {response.status_code}")
        except Exception as e:
            error_count += 1
            print(f"❌ 發生錯誤: {e}")

        time.sleep(interval)  # 等待指定間隔時間

    print(f"✅ 成功請求: {success_count} 次 | ❌ 失敗請求: {error_count} 次")

    if error_count > 0:
        print(f"⚠️ API 在 {interval} 秒頻率下出現錯誤，請考慮較低頻率")
        break
