#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Docker 镜像加速器测试 Web 应用
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import urllib.request
import urllib.error
import json
import threading
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import redis
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)
CORS(app)

# 数据库和 Redis 配置
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'mirror_checker'),
    'password': os.getenv('MYSQL_PASSWORD', 'mirror_checker_pass'),
    'database': os.getenv('MYSQL_DATABASE', 'mirror_checker'),
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': 0,
    'decode_responses': True
}

# Docker 配置路径
DOCKER_DAEMON_JSON = os.getenv('DOCKER_DAEMON_JSON', '/etc/docker/daemon.json')
DOCKER_DAEMON_JSON_BACKUP = os.getenv('DOCKER_DAEMON_JSON_BACKUP', '/etc/docker/daemon.json.bak')
AUTO_UPDATE_DOCKER_CONFIG = os.getenv('AUTO_UPDATE_DOCKER_CONFIG', 'true').lower() == 'true'

# Redis 连接池
redis_pool = None
redis_client = None

# 初始化 Redis
def init_redis():
    global redis_pool, redis_client
    try:
        redis_pool = redis.ConnectionPool(**REDIS_CONFIG)
        redis_client = redis.Redis(connection_pool=redis_pool)
        redis_client.ping()
        print("Redis 连接成功")
    except Exception as e:
        print(f"Redis 连接失败: {e}")
        redis_client = None

# 获取 MySQL 连接
def get_mysql_connection():
    try:
        return pymysql.connect(**MYSQL_CONFIG)
    except Exception as e:
        print(f"MySQL 连接失败: {e}")
        return None

# 默认镜像站列表
DEFAULT_MIRRORS = [
    "https://docker.1ms.run",
    "https://docker.1panel.live",
    "https://docker.m.ixdev.cn",
    "https://hub.rat.dev",
    "https://docker.xuanyuan.me",
    "https://dockerproxy.net",
    "https://docker.hlmirror.com",
    "https://hub1.nat.tf",
    "https://hub2.nat.tf",
    "https://hub3.nat.tf",
    "https://hub4.nat.tf",
    "https://docker.m.daocloud.io",
    "https://docker.kejilion.pro",
    "https://hub.1panel.dev",
    "https://dockerproxy.cool",
    "https://proxy.vvvv.ee",
    "https://dockerproxy.com",
    "https://docker.mirrors.ustc.edu.cn",
    "https://docker.nju.edu.cn"
]

# 测试结果缓存
test_results_cache: Dict = {
    "results": [],
    "total": 0,
    "available": 0,
    "unavailable": 0,
    "last_update": None,
    "next_update": None
}

# 定时任务锁，防止并发测试
test_lock = threading.Lock()


def test_mirror(mirror: str, timeout: int = 5) -> Tuple[bool, str, int]:
    """
    测试镜像加速器是否可用
    返回: (是否可用, 状态信息, HTTP状态码)
    """
    test_urls = [
        f"{mirror}/v2/",
        f"{mirror}",
    ]
    
    for test_url in test_urls:
        try:
            req = urllib.request.Request(test_url)
            req.add_header('User-Agent', 'Docker-Mirror-Checker/1.0')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                # 200, 301, 302, 401, 404 都表示服务可用
                if status_code in [200, 301, 302, 401, 404]:
                    return True, "可用", status_code
                elif status_code == 403:
                    return True, "可用（需要认证）", status_code
        except urllib.error.HTTPError as e:
            # HTTP 错误但服务存在
            if e.code in [401, 403, 404]:
                return True, f"可用（HTTP {e.code}）", e.code
            return False, f"HTTP 错误: {e.code}", e.code
        except urllib.error.URLError as e:
            continue
        except Exception as e:
            continue
    
    return False, "连接失败", 0


def test_mirror_detailed(mirror: str, timeout: int = 5, save_to_db: bool = True) -> Dict:
    """详细测试镜像加速器"""
    start_time = datetime.now()
    is_available, status_msg, status_code = test_mirror(mirror, timeout)
    end_time = datetime.now()
    response_time = (end_time - start_time).total_seconds() * 1000  # 毫秒
    
    result = {
        "mirror": mirror,
        "available": is_available,
        "status": status_msg,
        "status_code": status_code,
        "response_time": round(response_time, 2),
        "test_time": end_time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 保存到数据库
    if save_to_db:
        save_test_result_to_db(result)
    
    return result


def save_test_result_to_db(result: Dict):
    """保存测试结果到 MySQL"""
    conn = get_mysql_connection()
    if not conn:
        return
    
    try:
        with conn.cursor() as cursor:
            # 插入测试历史记录
            sql = """
                INSERT INTO mirror_test_history 
                (mirror_url, available, status, status_code, response_time, test_time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                result['mirror'],
                result['available'],
                result['status'],
                result['status_code'],
                result['response_time'],
                datetime.strptime(result['test_time'], '%Y-%m-%d %H:%M:%S')
            ))
            
            # 更新统计信息
            sql_stat = """
                INSERT INTO mirror_statistics 
                (mirror_url, total_tests, success_count, fail_count, avg_response_time, 
                 last_success_time, last_fail_time, current_status)
                VALUES (%s, 1, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    total_tests = total_tests + 1,
                    success_count = success_count + %s,
                    fail_count = fail_count + %s,
                    avg_response_time = (avg_response_time * (total_tests - 1) + %s) / total_tests,
                    last_success_time = IF(%s = 1, %s, last_success_time),
                    last_fail_time = IF(%s = 0, %s, last_fail_time),
                    current_status = %s
            """
            test_time = datetime.strptime(result['test_time'], '%Y-%m-%d %H:%M:%S')
            cursor.execute(sql_stat, (
                result['mirror'],
                1 if result['available'] else 0,
                0 if result['available'] else 1,
                result['response_time'],
                test_time if result['available'] else None,
                test_time if not result['available'] else None,
                result['available'],
                1 if result['available'] else 0,
                0 if result['available'] else 1,
                result['response_time'],
                1 if result['available'] else 0,
                test_time,
                1 if result['available'] else 0,
                test_time,
                result['available']
            ))
        
        conn.commit()
    except Exception as e:
        print(f"保存到数据库失败: {e}")
        conn.rollback()
    finally:
        conn.close()


def test_all_mirrors_background(mirrors: List[str] = None, save_to_db: bool = True) -> Dict:
    """后台测试所有镜像站（用于定时任务）"""
    if mirrors is None:
        mirrors = DEFAULT_MIRRORS
    
    results = []
    batch_time = datetime.now()
    
    # 使用线程池并行测试
    def test_worker(mirror):
        result = test_mirror_detailed(mirror, save_to_db=save_to_db)
        results.append(result)
    
    threads = []
    for mirror in mirrors:
        thread = threading.Thread(target=test_worker, args=(mirror,))
        thread.start()
        threads.append(thread)
    
    # 等待所有线程完成
    for thread in threads:
        thread.join(timeout=10)  # 每个线程最多等待10秒
    
    # 按可用性排序：可用的在前
    results.sort(key=lambda x: (not x['available'], x['response_time']))
    
    test_result = {
        "results": results,
        "total": len(results),
        "available": sum(1 for r in results if r['available']),
        "unavailable": sum(1 for r in results if not r['available'])
    }
    
    # 保存批次信息到数据库
    if save_to_db:
        save_batch_to_db(batch_time, test_result)
    
    # 缓存到 Redis（1小时过期）
    cache_to_redis(test_result)
    
    # 自动更新 Docker 配置
    if AUTO_UPDATE_DOCKER_CONFIG:
        auto_update_docker_config(test_result)
    
    return test_result


def save_batch_to_db(batch_time: datetime, test_result: Dict):
    """保存检测批次到数据库"""
    conn = get_mysql_connection()
    if not conn:
        return
    
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO test_batches 
                (batch_time, total_mirrors, available_count, unavailable_count)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (
                batch_time,
                test_result['total'],
                test_result['available'],
                test_result['unavailable']
            ))
        conn.commit()
    except Exception as e:
        print(f"保存批次信息失败: {e}")
        conn.rollback()
    finally:
        conn.close()


def cache_to_redis(data: Dict):
    """缓存数据到 Redis"""
    if not redis_client:
        return
    
    try:
        cache_key = "mirror_test_results"
        cache_data = {
            "results": data["results"],
            "total": data["total"],
            "available": data["available"],
            "unavailable": data["unavailable"],
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "next_update": (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        }
        redis_client.setex(
            cache_key,
            3600,  # 1小时过期
            json.dumps(cache_data, ensure_ascii=False)
        )
    except Exception as e:
        print(f"Redis 缓存失败: {e}")


def get_from_redis() -> Optional[Dict]:
    """从 Redis 获取缓存数据"""
    if not redis_client:
        return None
    
    try:
        cache_key = "mirror_test_results"
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"从 Redis 获取数据失败: {e}")
    
    return None


def auto_update_docker_config(test_result: Dict):
    """自动更新 Docker daemon.json 配置"""
    try:
        # 筛选可用的镜像源
        available = [r for r in test_result.get("results", []) if r.get('available', False)]
        
        if not available:
            print("没有可用的镜像源，跳过配置更新")
            return
        
        # 按响应时间排序，选择最快的 5 个
        sorted_available = sorted(available, key=lambda x: x.get('response_time', 9999))
        recommended = sorted_available[:5]
        
        # 生成配置
        config = {
            "registry-mirrors": [r['mirror'] for r in recommended]
        }
        
        # 检查配置文件是否存在
        config_dir = os.path.dirname(DOCKER_DAEMON_JSON)
        if not os.path.exists(config_dir):
            print(f"配置目录不存在: {config_dir}，尝试创建...")
            try:
                os.makedirs(config_dir, exist_ok=True)
            except Exception as e:
                print(f"创建配置目录失败: {e}")
                return
        
        # 备份现有配置
        if os.path.exists(DOCKER_DAEMON_JSON):
            try:
                shutil.copy2(DOCKER_DAEMON_JSON, DOCKER_DAEMON_JSON_BACKUP)
                print(f"已备份现有配置到: {DOCKER_DAEMON_JSON_BACKUP}")
            except Exception as e:
                print(f"备份配置失败: {e}")
        
        # 读取现有配置（如果存在）
        existing_config = {}
        if os.path.exists(DOCKER_DAEMON_JSON):
            try:
                with open(DOCKER_DAEMON_JSON, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            except Exception as e:
                print(f"读取现有配置失败: {e}，将创建新配置")
        
        # 合并配置（保留其他设置）
        existing_config["registry-mirrors"] = config["registry-mirrors"]
        
        # 写入新配置
        try:
            with open(DOCKER_DAEMON_JSON, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=4, ensure_ascii=False)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Docker 配置已自动更新: {DOCKER_DAEMON_JSON}")
            print(f"已配置 {len(recommended)} 个镜像源: {', '.join([r['mirror'] for r in recommended])}")
            
            # 尝试重启 Docker 服务（需要特殊权限）
            restart_docker_service()
            
        except PermissionError:
            print(f"⚠️  权限不足，无法写入 {DOCKER_DAEMON_JSON}")
            print("请确保容器有权限访问该文件，或使用 volume 挂载")
        except Exception as e:
            print(f"写入配置失败: {e}")
            
    except Exception as e:
        print(f"自动更新 Docker 配置失败: {e}")


def restart_docker_service():
    """尝试重启 Docker 服务"""
    try:
        # 检查是否有 systemctl 命令
        if shutil.which('systemctl'):
            # 在容器内无法直接重启宿主机的 Docker，所以只输出提示
            print("💡 提示: 配置已更新，请手动执行以下命令重启 Docker:")
            print("  sudo systemctl daemon-reload")
            print("  sudo systemctl restart docker")
        else:
            # 尝试使用其他方式
            print("💡 提示: 配置已更新，请重启 Docker 服务以使配置生效")
    except Exception as e:
        print(f"检查 Docker 服务状态失败: {e}")


def scheduled_test():
    """定时测试任务（每1小时执行一次）"""
    global test_results_cache
    
    if test_lock.acquire(blocking=False):
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始定时检测镜像源状态...")
            
            # 执行测试（保存到数据库）
            test_result = test_all_mirrors_background(save_to_db=True)
            
            # 更新内存缓存
            now = datetime.now()
            next_update = datetime.fromtimestamp(now.timestamp() + 3600)  # 1小时后
            
            test_results_cache = {
                "results": test_result["results"],
                "total": test_result["total"],
                "available": test_result["available"],
                "unavailable": test_result["unavailable"],
                "last_update": now.strftime("%Y-%m-%d %H:%M:%S"),
                "next_update": next_update.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时检测完成: 可用 {test_result['available']}/{test_result['total']} 个镜像源")
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 定时检测出错: {str(e)}")
        finally:
            test_lock.release()
    
    # 安排下一次测试（1小时后）
    timer = threading.Timer(3600.0, scheduled_test)
    timer.daemon = True
    timer.start()


def start_scheduled_test():
    """启动定时测试任务"""
    # 立即执行一次测试
    scheduled_test()


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/mirrors', methods=['GET'])
def get_mirrors():
    """获取镜像站列表"""
    mirrors = request.args.get('mirrors')
    if mirrors:
        try:
            mirror_list = json.loads(mirrors)
            return jsonify({"mirrors": mirror_list})
        except:
            pass
    return jsonify({"mirrors": DEFAULT_MIRRORS})


@app.route('/api/test', methods=['POST'])
def test_single():
    """测试单个镜像站"""
    data = request.get_json()
    mirror = data.get('mirror')
    
    if not mirror:
        return jsonify({"error": "缺少 mirror 参数"}), 400
    
    result = test_mirror_detailed(mirror)
    return jsonify(result)


@app.route('/api/test/all', methods=['POST'])
def test_all():
    """测试所有镜像站（实时测试）"""
    data = request.get_json()
    mirrors = data.get('mirrors', DEFAULT_MIRRORS)
    
    if not isinstance(mirrors, list):
        return jsonify({"error": "mirrors 必须是列表"}), 400
    
    results = []
    
    # 使用线程池并行测试（限制并发数）
    def test_worker(mirror):
        result = test_mirror_detailed(mirror)
        results.append(result)
    
    threads = []
    for mirror in mirrors:
        thread = threading.Thread(target=test_worker, args=(mirror,))
        thread.start()
        threads.append(thread)
    
    # 等待所有线程完成
    for thread in threads:
        thread.join(timeout=10)  # 每个线程最多等待10秒
    
    # 按可用性排序：可用的在前
    results.sort(key=lambda x: (not x['available'], x['response_time']))
    
    return jsonify({
        "results": results,
        "total": len(results),
        "available": sum(1 for r in results if r['available']),
        "unavailable": sum(1 for r in results if not r['available'])
    })


@app.route('/api/test/cached', methods=['GET'])
def get_cached_results():
    """获取缓存的测试结果（优先从 Redis，其次内存缓存）"""
    # 先尝试从 Redis 获取
    redis_data = get_from_redis()
    if redis_data:
        return jsonify(redis_data)
    
    # 如果 Redis 没有，使用内存缓存
    return jsonify(test_results_cache)


@app.route('/api/config/recommended', methods=['GET'])
def get_recommended_config():
    """获取推荐的 Docker 配置（基于最新的检测结果，优先从 Redis）"""
    # 先尝试从 Redis 获取
    redis_data = get_from_redis()
    if redis_data:
        results = redis_data.get("results", [])
        last_update = redis_data.get("last_update")
        next_update = redis_data.get("next_update")
    else:
        # 从内存缓存获取
        results = test_results_cache.get("results", [])
        last_update = test_results_cache.get("last_update")
        next_update = test_results_cache.get("next_update")
    
    if not results:
        return jsonify({
            "error": "暂无检测数据",
            "config": None
        })
    
    # 筛选可用的镜像源
    available = [r for r in results if r.get('available', False)]
    
    if not available:
        return jsonify({
            "error": "暂无可用的镜像源",
            "config": None
        })
    
    # 按响应时间排序，选择最快的 5 个
    sorted_available = sorted(available, key=lambda x: x.get('response_time', 9999))
    recommended = sorted_available[:5]
    
    # 生成配置
    config = {
        "registry-mirrors": [r['mirror'] for r in recommended]
    }
    
    return jsonify({
        "config": config,
        "mirrors": [r['mirror'] for r in recommended],
        "count": len(recommended),
        "total_available": len(available),
        "last_update": last_update,
        "next_update": next_update
    })


@app.route('/api/config/update', methods=['POST'])
def update_docker_config_manual():
    """手动触发更新 Docker 配置"""
    try:
        # 获取最新的检测结果
        redis_data = get_from_redis()
        if redis_data:
            test_result = {
                "results": redis_data.get("results", []),
                "total": redis_data.get("total", 0),
                "available": redis_data.get("available", 0),
                "unavailable": redis_data.get("unavailable", 0)
            }
        else:
            test_result = {
                "results": test_results_cache.get("results", []),
                "total": test_results_cache.get("total", 0),
                "available": test_results_cache.get("available", 0),
                "unavailable": test_results_cache.get("unavailable", 0)
            }
        
        if not test_result.get("results"):
            return jsonify({
                "error": "暂无检测数据，请先执行检测",
                "success": False
            }), 400
        
        # 执行自动更新
        auto_update_docker_config(test_result)
        
        return jsonify({
            "success": True,
            "message": "Docker 配置已更新",
            "config_path": DOCKER_DAEMON_JSON
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取历史检测记录"""
    mirror_url = request.args.get('mirror')
    limit = int(request.args.get('limit', 100))
    
    conn = get_mysql_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        with conn.cursor() as cursor:
            if mirror_url:
                sql = """
                    SELECT * FROM mirror_test_history 
                    WHERE mirror_url = %s 
                    ORDER BY test_time DESC 
                    LIMIT %s
                """
                cursor.execute(sql, (mirror_url, limit))
            else:
                sql = """
                    SELECT * FROM mirror_test_history 
                    ORDER BY test_time DESC 
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
            
            results = cursor.fetchall()
            
            # 转换 datetime 为字符串
            for r in results:
                if r.get('test_time'):
                    r['test_time'] = r['test_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({"history": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """获取镜像源统计信息"""
    conn = get_mysql_connection()
    if not conn:
        return jsonify({"error": "数据库连接失败"}), 500
    
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT * FROM mirror_statistics 
                ORDER BY success_count DESC, avg_response_time ASC
            """
            cursor.execute(sql)
            results = cursor.fetchall()
            
            # 转换 datetime 为字符串
            for r in results:
                if r.get('last_success_time'):
                    r['last_success_time'] = r['last_success_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('last_fail_time'):
                    r['last_fail_time'] = r['last_fail_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('updated_at'):
                    r['updated_at'] = r['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({"statistics": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/api/test/batch', methods=['POST'])
def test_batch():
    """批量测试镜像站（带进度）"""
    data = request.get_json()
    mirrors = data.get('mirrors', DEFAULT_MIRRORS)
    
    if not isinstance(mirrors, list):
        return jsonify({"error": "mirrors 必须是列表"}), 400
    
    results = []
    completed = 0
    
    for mirror in mirrors:
        result = test_mirror_detailed(mirror)
        results.append(result)
        completed += 1
        
        # 返回进度（流式响应）
        yield f"data: {json.dumps({'progress': completed, 'total': len(mirrors), 'result': result})}\n\n"
    
    # 最终结果
    results.sort(key=lambda x: (not x['available'], x['response_time']))
    yield f"data: {json.dumps({'done': True, 'results': results, 'total': len(results), 'available': sum(1 for r in results if r['available']), 'unavailable': sum(1 for r in results if not r['available'])})}\n\n"


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    # 初始化 Redis
    print("初始化 Redis 连接...")
    init_redis()
    
    # 尝试从 Redis 加载缓存
    cached_data = get_from_redis()
    if cached_data:
        test_results_cache.update(cached_data)
        print("从 Redis 加载缓存数据成功")
    
    # 启动定时测试任务
    print("启动定时检测任务（每1小时检测一次）...")
    start_scheduled_test()
    
    # 启动 Flask 应用
    app.run(host='0.0.0.0', port=5000, debug=False)

