"""
几个抓取脚本共用的小工具：
- 带自动重试的网络请求
- "剧组类岗位"过滤规则
- 读取上一次结果 / 标记新职位 / 保存文件

每个网站的抓取脚本（shixiseng.py、tencent.py、kuaishou.py）只需要负责
"怎么从这个网站拿到职位列表"，剩下的通用逻辑都从这里调用，避免三份代码
各写一套、以后改起来要改三个地方。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 每次请求之间的等待秒数，避免请求过快给网站造成压力
REQUEST_DELAY_SECONDS = 1.5

# 职位名称里如果包含下面这些词，判定为"剧组"类现场岗位，会被剔除
EXCLUDE_TITLE_KEYWORDS = [
    "剧组", "场务", "场记", "选角", "置景", "剧务", "横店", "跟组",
]

# 传媒方向的搜索关键词（用于向网站发起搜索）
MEDIA_KEYWORDS = [
    "新媒体运营", "短视频", "视频剪辑", "商业摄影",
    "直播", "内容策划", "文案", "短剧",
]

# AI 相关的搜索关键词。你说"沾点边的 AI 都可以"，所以这里既包含
# 纯 AI 岗位，也包含"AI + 内容/视频"这种和传媒专业结合的方向
AI_KEYWORDS = [
    "AI", "AIGC", "人工智能", "大模型", "多模态",
    "AI视频", "AI内容", "AI产品", "生成式", "数据标注",
]

# 所有抓取脚本统一用这一份关键词
SEARCH_KEYWORDS = MEDIA_KEYWORDS + AI_KEYWORDS

# 判断"是否提供转正机会"时，在职位标题/描述里找这些词
FULLTIME_HINT_KEYWORDS = ["可转正", "转正", "留用", "提前批"]


def looks_like_fulltime_track(*texts: str | None) -> bool:
    """从职位标题、描述等文字里判断这个实习是不是有转正机会"""
    blob = " ".join(t for t in texts if t)
    return any(kw in blob for kw in FULLTIME_HINT_KEYWORDS)


def get_with_retry(
    url: str,
    params: dict | None = None,
    method: str = "GET",
    json_body: dict | None = None,
    max_retries: int = 3,
) -> requests.Response:
    """访问网页/接口，如果因为网络问题失败，就自动重试几次再放弃"""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(REQUEST_DELAY_SECONDS * attempt)
    raise last_error


def is_excluded(title: str | None) -> bool:
    """职位名称里是否包含剧组类关键词"""
    if not title:
        return False
    return any(kw in title for kw in EXCLUDE_TITLE_KEYWORDS)


def load_previous_jobs(output_file: Path) -> dict:
    """读取上一次抓取保存的结果，用来判断哪些是"新职位" """
    if not output_file.exists():
        return {}
    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {job["id"]: job for job in data.get("jobs", [])}


def mark_new_and_save(jobs: dict, output_file: Path, excluded_count: int = 0) -> dict:
    """给职位标记"是否新出现"，然后存成 JSON 文件"""
    previous_jobs = load_previous_jobs(output_file)
    today = datetime.now().strftime("%Y-%m-%d")

    for job_id, job in jobs.items():
        if job_id in previous_jobs:
            job["first_seen"] = previous_jobs[job_id].get("first_seen", today)
            job["is_new"] = False
        else:
            job["first_seen"] = today
            job["is_new"] = True

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "job_count": len(jobs),
        "excluded_count": excluded_count,
        "jobs": list(jobs.values()),
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
