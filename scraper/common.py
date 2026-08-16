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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# 抓取脚本实际是在 GitHub 的服务器上跑的，那台机器用的是"世界标准时间"，
# 比北京时间早 8 小时。如果不特意转换，存进 JSON 里的时间会是 UTC 时间，
# 人看着容易理解错（比如凌晨2点其实是北京时间上午10点）。
# 所以这里统一用北京时间来记录"什么时候抓的"。
BEIJING_TZ = timezone(timedelta(hours=8))


def now_beijing() -> datetime:
    """当前的北京时间"""
    return datetime.now(BEIJING_TZ)

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

# 职位名称里如果包含下面这些词，说明是需要计算机/理工科背景才能干的
# 技术岗（写代码、调模型、搞算法），传媒/文科背景投不了，要排除掉。
# 像"AI训练师""AI产品经理""数据标注"这类不用写代码的 AI 相关工作
# 不在这个名单里，会被保留。
HARD_TECH_KEYWORDS = [
    # 算法 / 建模类
    "算法", "模型训练", "深度学习", "机器学习", "神经网络", "强化学习",
    "预训练", "推理优化", "训练框架", "计算机视觉", "自然语言处理",
    "语音识别", "推荐系统", "知识图谱", "SLAM", "推理", "算子",
    "研究员", "评测工程师",
    # 软件开发 / 工程类
    # "工程师"这个词单独放在这里就够了：实际数据里检查过，
    # 凡是标题带"工程师"的，不管前面接的是硬件、芯片、测试、AI、
    # 大模型什么方向，清一色都是需要理工科背景的岗位，没有例外。
    "工程师", "后端", "前端", "客户端", "全栈",
    "架构", "嵌入式", "驱动开发", "编译器", "测试开发",
    "运维", "服务端", "数据仓库", "数仓", "SRE", "Infra",
    "分布式系统", "图形学", "芯片", "硬件设计", "电路",
    # 直接点名编程语言/技术栈的
    "C++", "Java开发", "Python开发", "CUDA", "GPU",
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
    """职位名称里是否包含剧组类关键词，或者需要理工科背景的硬核技术关键词"""
    if not title:
        return False
    if any(kw in title for kw in EXCLUDE_TITLE_KEYWORDS):
        return True
    return any(kw in title for kw in HARD_TECH_KEYWORDS)


# 每天工资低于这个数的日常实习，质量通常比较差，直接不展示
MIN_DAILY_SALARY = 80


def salary_too_low(salary_text: str | None, threshold: int = MIN_DAILY_SALARY) -> bool:
    """薪资格式类似"100-150/天"，取最低那个数字判断是否低于门槛。
    没有薪资信息的（None）不算"太低"，只排除明确写了低薪的。"""
    if not salary_text:
        return False
    import re

    m = re.match(r"\s*(\d+)", salary_text)
    if not m:
        return False
    return int(m.group(1)) < threshold


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
    today = now_beijing().strftime("%Y-%m-%d")

    for job_id, job in jobs.items():
        if job_id in previous_jobs:
            job["first_seen"] = previous_jobs[job_id].get("first_seen", today)
            job["is_new"] = False
        else:
            job["first_seen"] = today
            job["is_new"] = True

    result = {
        "updated_at": now_beijing().strftime("%Y-%m-%d %H:%M:%S"),
        "job_count": len(jobs),
        "excluded_count": excluded_count,
        "jobs": list(jobs.values()),
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
