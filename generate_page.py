import json
import urllib.request
from datetime import datetime
import os

mirrors_file = os.path.join(os.path.dirname(__file__), 'docker-mirror-checker', 'mirrors.json')
with open(mirrors_file, 'r') as f:
    MIRRORS = json.load(f)

def test_mirror(mirror, timeout=5):
    test_urls = [f"{mirror}/v2/", mirror]
    for test_url in test_urls:
        try:
            req = urllib.request.Request(test_url)
            req.add_header('User-Agent', 'Docker-Mirror-Test/1.0')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.getcode() in [200, 301, 302, 401, 404]:
                    return True, response.getcode()
        except Exception:
            continue
    return False, None

results = []
for mirror in MIRRORS:
    is_valid, status = test_mirror(mirror)
    results.append({"mirror": mirror, "status": status, "available": is_valid})

html = '<!DOCTYPE html>\n<html lang="zh-CN>\n<head>\n    <meta charset="UTF-8">\n    <title>Docker 镜像加速器测试结果</title>\n</head>\n<body>\n    <h1>Docker 镜像加速器测试结果</h1>\n    <p>最后更新: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '</p>\n    <h3>可用的镜像加速器</h3>\n    <ul>\n'
for r in results:
    if r["available"]:
        html += f'<li><a href="{r["mirror"]}">{r["mirror"]}</a></li>\n'
html += '    </ul>\n    <h3>不可用的镜像加速器</h3>\n    <ul>\n'
for r in results:
    if not r["available"]:
        html += f'<li>{r["mirror"]}</li>\n'
html += '    </ul>\n    <p>由 GitHub Actions 自动更新</p>\n</body>\n</html>'

with open('docs/index.html', 'w') as f:
    f.write(html)