"""
网易官网招聘抓取脚本

网易的招聘官网（hr.163.com）有一个公开、没有任何加密/签名保护的数据接口，
关键词搜索是真的会在服务器那边生效的（会搜标题、也会搜职位描述，所以搜到的
职位有时候标题里不带关键词，但实际内容是相关的，比如搜"短视频"能搜到"新媒体
剪辑实习生"这种）。

这里固定用 workType=1，对应网易官网自己分类里的"日常实习生"。
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import common

QUERY_URL = "https://hr.163.com/api/hr163/position/queryPage"
DETAIL_URL = "https://hr.163.com/job-detail.html?id={id}&lang=zh"

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
OUTPUT_FILE = DATA_DIR / "jobs_netease.json"

WORK_TYPE_DAILY_INTERN = "1"


def fetch_jobs_for_keyword(keyword: str, page_size: int = 50) -> list[dict]:
    body = {
        "pageNo": 1,
        "pageSize": page_size,
        "workType": WORK_TYPE_DAILY_INTERN,
        "keyword": keyword,
    }
    resp = common.get_with_retry(QUERY_URL, method="POST", json_body=body)
    data = resp.json()
    posts = ((data.get("data") or {}).get("list")) or []

    jobs = []
    for post in posts:
        title = post.get("name")
        requirement = post.get("requirement") or ""
        description = post.get("description") or ""
        offers_fulltime = "转正" in (title or "") or "转正" in requirement or "转正" in description

        update_ms = post.get("updateTime")
        publish_date = (
            datetime.fromtimestamp(update_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
            if update_ms
            else None
        )

        tags = [t for t in [post.get("reqEducationName"), post.get("reqWorkYearsName")] if t]

        jobs.append(
            {
                "id": f"netease_{post['id']}",
                "title": title,
                "company": post.get("productName") or "网易",
                "city": "/".join(post.get("workPlaceNameList") or []) or None,
                "industry": post.get("firstPostTypeName"),
                "tags": tags,
                "link": DETAIL_URL.format(id=post["id"]),
                "search_keyword": keyword,
                "source": "网易招聘",
                "publish_date": publish_date,
                "salary": None,
                "offers_fulltime": offers_fulltime,
                "is_campus_official": True,
            }
        )
    return jobs


def run(keywords: list[str]) -> dict:
    all_jobs = {}
    excluded_count = 0

    for i, keyword in enumerate(keywords):
        if i > 0:
            time.sleep(common.REQUEST_DELAY_SECONDS)
        try:
            jobs = fetch_jobs_for_keyword(keyword)
        except Exception as e:
            print(f"关键词「{keyword}」抓取失败，跳过：{e}")
            continue

        for job in jobs:
            if common.is_excluded(job["title"]):
                excluded_count += 1
                continue
            all_jobs[job["id"]] = job

    return common.mark_new_and_save(all_jobs, OUTPUT_FILE, excluded_count)


if __name__ == "__main__":
    result = run(common.SEARCH_KEYWORDS)
    print(f"抓到 {result['job_count']} 个职位，已保存到 {OUTPUT_FILE}")
    print(f"过滤掉剧组类岗位 {result['excluded_count']} 个")
    new_count = sum(1 for j in result["jobs"] if j["is_new"])
    fulltime_count = sum(1 for j in result["jobs"] if j["offers_fulltime"])
    print(f"其中「新职位」有 {new_count} 个，标题/描述里提到“转正”的有 {fulltime_count} 个")
