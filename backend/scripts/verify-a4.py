#!/usr/bin/env python3
"""
A4 页面快速验证脚本

验证 settings-provider.html, capture.html, tasks.html 三个页面：
- 静态文件可访问
- API 端点响应正常
- 页面包含关键元素
"""

import sys
import time
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8787"

def check_page(path: str, expected_keywords: list[str]) -> bool:
    """检查页面是否可访问且包含关键词"""
    url = f"{BASE_URL}{path}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            print(f"❌ {path} - HTTP {response.status_code}")
            return False
        
        content = response.text
        missing = [kw for kw in expected_keywords if kw not in content]
        
        if missing:
            print(f"❌ {path} - 缺少关键词: {missing}")
            return False
        
        print(f"✅ {path}")
        return True
    except Exception as e:
        print(f"❌ {path} - {e}")
        return False

def check_api(path: str) -> bool:
    """检查 API 端点是否响应"""
    url = f"{BASE_URL}{path}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code not in [200, 503]:  # 503 for readiness when not ready
            print(f"❌ API {path} - HTTP {response.status_code}")
            return False
        
        print(f"✅ API {path}")
        return True
    except Exception as e:
        print(f"❌ API {path} - {e}")
        return False

def main():
    print("🔍 验证 A4 页面...\n")
    
    # 检查服务器是否运行
    try:
        requests.get(f"{BASE_URL}/api/liveness", timeout=2)
        print("✅ 服务器运行中\n")
    except:
        print("❌ 服务器未运行")
        print("请先启动服务器:")
        print("  cd H:/studybuddy/backend")
        print("  C:/miniconda/py310/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787")
        return 1
    
    results = []
    
    # 检查页面
    print("📄 检查页面...")
    results.append(check_page(
        "/app/settings-provider.html",
        ["Provider 能力状态", "配置写入契约尚未完成批准", "data-od-id"]
    ))
    
    results.append(check_page(
        "/app/capture.html",
        ["课堂采集", "真实 ASR", "新建采集会话", "data-od-id"]
    ))
    
    results.append(check_page(
        "/app/tasks.html",
        ["任务状态", "embedding_index", "data-od-id"]
    ))
    
    # 检查 API
    print("\n🔌 检查 API...")
    results.append(check_api("/api/ai/capabilities"))
    results.append(check_api("/api/readiness"))
    results.append(check_api("/api/study/capture-sessions"))
    
    # 检查导航
    print("\n🧭 检查导航...")
    results.append(check_page(
        "/app/today.html",
        ["采集", "设置"]  # 检查新增的导航项
    ))
    
    # 总结
    print("\n" + "="*50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ 全部通过 ({passed}/{total})")
        return 0
    else:
        print(f"❌ 部分失败 ({passed}/{total})")
        return 1

if __name__ == "__main__":
    sys.exit(main())
