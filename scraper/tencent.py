"""
腾讯官网校招抓取脚本

腾讯招聘官网（careers.tencent.com）有一个公开的数据接口，不需要登录、
不需要破解任何加密，直接按关键词搜索就能拿到结构完整的职位数据
（真实职位名称、发布日期、职位分类都是明文，比实习僧那边好拿多了）。

这个接口是"社招+校招"共用的，所以每次请求都带上 attrId=2,3，
表示只要"校招应届生"和"校招实习生"这两类，把社招过滤掉。
"""

from __future__ import annotations

import time
from pathlib import Path

import common

QUERY_URL = "https://careers.tencent.com/tencentcareer/api/post/Query"

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
OUTPUT_FILE = DATA_DIR / "jobs_tencent.json"

# attrId: 2=校招应届生 3=校招实习生（1=社招，这里不要）
CAMPUS_ATTR_IDS = "2,3"


def fetch_jobs_for_keyword(keyword: str, page_size: int = 30) -> list[dict]:
    params = {
        "timestamp": "0",
        "countryId": "",
        "cityId": "",
        "bgIds": "",
        "productId": "",
        "categoryId": "",
        "parentCategoryId": "",
        "attrId": CAMPUS_ATTR_IDS,
        "keyword": keyword,
        "pageIndex": 1,
        "pageSize": page_size,
        "language": "zh-cn",
        "area": "cn",
    }
    resp = common.get_with_retry(QUERY_URL, params=params)
    data = resp.json()
    posts = (data.get("Data") or {}).get("Posts") or []

    jobs = []
    for post in posts:
        tags = [t for t in [post.get("BGName"), post.get("RequireWorkYearsName")] if t]
        jobs.append(
            {
                "id": f"tencent_{post['PostId']}",
                "title": post.get("RecruitPostName"),
                "company": "腾讯",
                "city": post.get("LocationName"),
                "industry": post.get("CategoryName"),
                "tags": tags,
                "link": post.get("PostURL"),
                "search_keyword": keyword,
                "source": "腾讯招聘",
                "publish_date": post.get("LastUpdateTime"),
                "salary": None,
                "offers_fulltime": False,
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
    print(f"其中「新职位」有 {new_count} 个")
