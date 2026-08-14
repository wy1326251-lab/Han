"""
一键运行所有抓取脚本

这个文件是"总开关"：跑一次它，就会依次去五个来源抓岗位。
GitHub 每天自动运行的也是这个文件。

设计上有意让它"不容易整个失败"：某一个网站临时抽风、改版或者超时了，
只会跳过那一个来源并留下记录，其他来源照常抓，不会因为一处出错就
让当天一条数据都更新不了。
"""

from __future__ import annotations

import importlib
import sys
import traceback
from datetime import datetime
from pathlib import Path

# 让这个文件能找到 scraper 文件夹里的脚本
sys.path.insert(0, str(Path(__file__).resolve().parent / "scraper"))

import common  # noqa: E402

# 每个来源写成 (显示名称, 模块名, 该模块 run() 需要的参数)
SOURCES = [
    ("实习僧", "shixiseng", lambda m: (common.SEARCH_KEYWORDS,)),
    ("网易招聘", "netease", lambda m: (common.SEARCH_KEYWORDS,)),
    ("腾讯招聘", "tencent", lambda m: (common.SEARCH_KEYWORDS,)),
    ("快手校招", "kuaishou", lambda m: (m.TITLE_KEYWORDS,)),
    ("Moka平台(各公司官网校招)", "moka", lambda m: (m.COMPANIES,)),
]


def main() -> int:
    print(f"===== 开始抓取 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

    total_jobs = 0
    total_new = 0
    failed = []

    for label, module_name, args_of in SOURCES:
        print(f"----- {label} -----")
        try:
            module = importlib.import_module(module_name)
            result = module.run(*args_of(module))
            new_count = sum(1 for j in result["jobs"] if j.get("is_new"))
            total_jobs += result["job_count"]
            total_new += new_count
            print(f"{label}：抓到 {result['job_count']} 个，其中新职位 {new_count} 个\n")
        except Exception:
            failed.append(label)
            print(f"{label}：抓取失败，跳过。原因如下：")
            traceback.print_exc()
            print()

    print("===== 抓取结束 =====")
    print(f"合计 {total_jobs} 个职位，其中今天新出现的 {total_new} 个")
    if failed:
        print(f"以下来源今天没抓成功：{'、'.join(failed)}")

    # 就算有个别来源失败，也算这次运行成功（避免 GitHub 报红），
    # 只有全部来源都失败时才当作真正的失败
    if failed and len(failed) == len(SOURCES):
        print("所有来源都失败了，可能是网络问题或者网站集体改版，需要检查。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
