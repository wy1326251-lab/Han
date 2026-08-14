"""
快手官网校招抓取脚本

快手校招官网（campus.kuaishou.cn）有一个公开的数据接口，不需要登录或
破解加密。但实测发现这个接口的"keyword"参数其实不生效（传什么关键词
结果都一样），所以做法改成：把"2027应届生"和"2027实习生"这两批当前
在招的岗位全部拿下来（一次请求就能拿完，量不大），再由我们自己在
职位名称里查找传媒相关的关键词进行筛选，而不是指望网站帮我们筛选。

职位名称里带"留用"字样的（比如"【留用实习】XXX"），说明有转正机会，
标记为 offers_fulltime。
"""

from __future__ import annotations

from pathlib import Path

import common

QUERY_URL = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"
DETAIL_URL = "https://campus.kuaishou.cn/#/campus/job-info/{id}"

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
OUTPUT_FILE = DATA_DIR / "jobs_kuaishou.json"

# 20271779425607 = 2027应届生批次，20271772783534 = 2027实习生批次
RECRUIT_SUB_PROJECT_CODES = ["20271779425607", "20271772783534"]

POSITION_NATURE_NAMES = {
    "fulltime": "全职",
    "intern": "实习",
    "parttime": "兼职",
}

# 快手接口的关键词搜索是失效的（传什么词返回结果都一样），所以做法是
# "把岗位全拿下来后自己按标题筛"，用的是比较短的词根
# （比如"视频"能同时匹配到"短视频""视频剪辑"）
TITLE_KEYWORDS = [
    "新媒体", "短视频", "视频", "剪辑", "摄影", "摄像",
    "直播", "内容", "文案", "短剧", "编导", "策划",
    "AI", "AIGC", "人工智能", "大模型", "多模态", "标注",
]

# 标题里带这些词的，基本是要写代码的技术岗蹭到了"视频""内容""AI"这类词
# （比如"音视频算法工程师"），需要计算机专业背景，所以排除掉。
# 注意：AI 产品、AI 内容、AIGC 这类不用写代码的岗位不在此列，会被保留。
TECH_TITLE_KEYWORDS = [
    "算法", "工程师", "开发", "架构", "后端", "前端", "客户端",
    "硬件", "测试", "数据科学",
]


def fetch_all_jobs(sub_project_code: str, page_size: int = 300) -> list[dict]:
    body = {
        "page": 1,
        "pageSize": page_size,
        "recruitSubProjectCodes": [sub_project_code],
    }
    resp = common.get_with_retry(QUERY_URL, method="POST", json_body=body)
    data = resp.json()
    return (data.get("result") or {}).get("list") or []


def to_job_dict(post: dict) -> dict:
    cities = [c.get("name") for c in (post.get("workLocationDicts") or []) if c.get("name")]
    nature = POSITION_NATURE_NAMES.get(post.get("positionNatureCode"), post.get("positionNatureCode"))
    title = post.get("name")

    return {
        "id": f"kuaishou_{post['id']}",
        "title": title,
        "company": "快手",
        "city": "/".join(cities) if cities else None,
        "industry": None,
        "tags": [t for t in [nature] if t],
        "link": DETAIL_URL.format(id=post["id"]),
        "search_keyword": None,
        "source": "快手校招",
        "publish_date": post.get("releaseTime"),
        "salary": None,
        "offers_fulltime": bool(title and "留用" in title),
    }


def run(media_keywords: list[str]) -> dict:
    all_jobs = {}
    excluded_count = 0

    raw_posts = []
    for code in RECRUIT_SUB_PROJECT_CODES:
        try:
            raw_posts.extend(fetch_all_jobs(code))
        except Exception as e:
            print(f"批次「{code}」抓取失败，跳过：{e}")

    for post in raw_posts:
        job = to_job_dict(post)
        title = job["title"] or ""

        if not any(kw in title for kw in media_keywords):
            continue  # 标题里没有传媒相关关键词，跳过
        if any(kw in title for kw in TECH_TITLE_KEYWORDS):
            continue  # 标题里带算法/工程师这类字眼，是技术岗蹭到了"视频""内容"这些词，不是传媒岗

        if common.is_excluded(title):
            excluded_count += 1
            continue

        all_jobs[job["id"]] = job

    return common.mark_new_and_save(all_jobs, OUTPUT_FILE, excluded_count)


if __name__ == "__main__":
    result = run(TITLE_KEYWORDS)
    print(f"抓到 {result['job_count']} 个职位，已保存到 {OUTPUT_FILE}")
    print(f"过滤掉剧组类岗位 {result['excluded_count']} 个")
    new_count = sum(1 for j in result["jobs"] if j["is_new"])
    fulltime_count = sum(1 for j in result["jobs"] if j["offers_fulltime"])
    print(f"其中「新职位」有 {new_count} 个，标题带“留用”的有 {fulltime_count} 个")
