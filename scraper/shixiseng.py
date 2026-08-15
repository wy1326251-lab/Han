"""
实习僧网站抓取脚本

流程：
1. 用普通的网络请求（伪装成浏览器）打开实习僧的搜索结果页，拿到公司名、
   城市、行业、福利标签、职位详情链接（这些是明文，能直接读到）
2. 对每个职位，额外访问一次它的详情页，取出：
   - 真实的职位名称（详情页的网页标题里藏着明文，不像列表页那样加密）
   - 是否提供转正机会、薪资区间
   （这两项在列表页会被网站用会变化的自定义字体加密，程序读不到，
   但详情页的网页标题、以及页面里一段压缩数据里能找到明文）
3. 交给 common.py 统一做"剔除剧组类岗位""标记新职位""保存文件"

因为每个职位都要多访问一次详情页，这个脚本跑起来比腾讯、快手那两个慢
（大概是"职位数量 x 1.5秒" 的时间），但请求量仍然是可控的、每天一两次的水平。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import common
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.shixiseng.com/interns"
DETAIL_URL = "https://www.shixiseng.com/intern/{id}"

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
OUTPUT_FILE = DATA_DIR / "jobs_shixiseng.json"

# 详情页标题格式一般是："职位名称 [ID12345]实习招聘-公司名实习生招聘-实习僧"
# 这个正则用来把后面的"ID号+网站固定后缀"去掉，只留职位名称
TITLE_PATTERN = re.compile(r"^(.*?)(?:\s*ID\d+)?实习招聘-")


def fetch_search_html(keyword: str) -> str:
    """访问搜索结果页，拿到网页的原始 HTML 内容"""
    resp = common.get_with_retry(SEARCH_URL, params={"keyword": keyword})
    return resp.text


def parse_job_cards(html: str, keyword: str) -> list[dict]:
    """从搜索结果页的 HTML 中，把每个职位卡片的信息挑出来"""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.intern-item")

    jobs = []
    for card in cards:
        intern_id = card.get("data-intern-id")
        if not intern_id:
            continue

        city_el = card.select_one(".intern-detail__job .city")
        city = city_el.get_text(strip=True) if city_el else ""

        company_el = card.select_one(".intern-detail__company .title")
        company = company_el.get("title", "").strip() if company_el else ""

        industry_el = card.select_one(".intern-detail__company p.tip .ellipsis")
        industry = industry_el.get_text(strip=True) if industry_el else ""

        tag_els = card.select(".advantage-wrap .intern-label")
        tags = [t.get_text(strip=True) for t in tag_els]

        jobs.append(
            {
                "id": intern_id,
                "title": None,
                "company": company,
                "city": city,
                "industry": industry,
                "tags": tags,
                "link": DETAIL_URL.format(id=intern_id),
                "search_keyword": keyword,
                "source": "实习僧",
                "publish_date": None,
            }
        )
    return jobs


def _find_matching_bracket(text: str, open_index: int) -> int:
    """给定 text[open_index] 是一个左括号（( { [ 之一），找到与它配对的右括号位置
    （会跳过字符串里的括号，避免被引号内的内容干扰）"""
    pairs = {"(": ")", "{": "}", "[": "]"}
    closers = [pairs[text[open_index]]]
    i = open_index + 1
    in_string = None
    escape = False
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
        elif ch in "\"'":
            in_string = ch
        elif ch in pairs:
            closers.append(pairs[ch])
        elif ch in (")", "}", "]"):
            closers.pop()
            if not closers:
                return i
        i += 1
    return -1


def _split_top_level(text: str) -> list[str]:
    """按最外层的逗号切分字符串，忽略括号、引号内部的逗号"""
    parts = []
    depth = 0
    in_string = None
    escape = False
    current = []
    for ch in text:
        if in_string:
            current.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            continue
        if ch in "\"'":
            in_string = ch
            current.append(ch)
        elif ch in "([{":
            depth += 1
            current.append(ch)
        elif ch in ")]}":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _build_nuxt_var_map(html: str) -> dict[str, str]:
    """
    详情页里嵌了一段这样的压缩 JS 代码：
        window.__NUXT__=(function(a,b,c,...){ ...用到 a,b,c 的地方... }(值1,值2,值3,...))
    这是页面框架（Nuxt.js）为了省流量，把页面里重复出现的值统一存成变量 a、b、c...，
    要拿到某个字段的真实值，有时候需要先知道 a、b、c 各自对应的原始内容。
    这个函数就是把"变量名 -> 原始内容"这张对照表建出来。
    """
    fn_idx = html.find("function(", html.find("__NUXT__="))
    if fn_idx == -1:
        return {}

    params_open = fn_idx + len("function")
    params_close = _find_matching_bracket(html, params_open)
    if params_close == -1:
        return {}
    param_names = [p.strip() for p in html[params_open + 1:params_close].split(",") if p.strip()]

    # 参数列表后面紧跟函数体 "{...}"
    body_open = params_close + 1
    if body_open >= len(html) or html[body_open] != "{":
        return {}
    body_close = _find_matching_bracket(html, body_open)
    if body_close == -1:
        return {}

    # 函数体后面紧跟真正传进去的值 "(值1,值2,...)"
    args_open = body_close + 1
    if args_open >= len(html) or html[args_open] != "(":
        return {}
    args_close = _find_matching_bracket(html, args_open)
    if args_close == -1:
        return {}

    arg_exprs = _split_top_level(html[args_open + 1:args_close])
    return dict(zip(param_names, arg_exprs))


def _resolve_js_value(raw: str, var_map: dict[str, str]) -> str | None:
    """把一段 JS 表达式（可能是字符串字面量，也可能是引用某个变量）解析成真正的文本值"""
    raw = raw.strip()
    if raw in ("void 0", "undefined", "null"):
        return None
    if raw.startswith('"') and raw.endswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw[1:-1]
    if re.fullmatch(r"[a-zA-Z_$][\w$]*", raw) and raw in var_map:
        return _resolve_js_value(var_map[raw], var_map)
    return None


def _extract_field(html: str, field: str, var_map: dict[str, str]) -> str | None:
    """从详情页里那段压缩过的 JS 数据中，取出类似 xx.chance="面议" 这样的字段值
    （字段前面的对象名每次访问网站都会变，所以不能写死成固定的字母）"""
    m = re.search(rf"\b[a-zA-Z_$][\w$]*\.{field}=([^;]+);", html)
    if not m:
        return None
    return _resolve_js_value(m.group(1), var_map)


def fetch_job_detail(intern_id: str) -> dict:
    """访问职位详情页，取出真实职位名称、转正信息、薪资"""
    url = DETAIL_URL.format(id=intern_id)
    resp = common.get_with_retry(url)
    html = resp.text

    title_match = re.search(r"<title>(.*?)</title>", html)
    raw_title = title_match.group(1) if title_match else ""
    cleaned = TITLE_PATTERN.match(raw_title)
    title = cleaned.group(1).strip() if cleaned else raw_title.strip()

    var_map = _build_nuxt_var_map(html)
    chance = _extract_field(html, "chance", var_map)  # 可转正 / 无转正 / 面议
    minsal = _extract_field(html, "minsal", var_map)
    maxsal = _extract_field(html, "maxsal", var_map)

    salary = None
    if minsal and maxsal:
        salary = f"{minsal}-{maxsal}/天"

    return {
        "title": title or None,
        "chance": chance,
        "offers_fulltime": chance == "可转正",
        "salary": salary,
    }


def run(keywords: list[str]) -> dict:
    # 第一步：把所有关键词的搜索结果收集起来，按 id 去重
    all_jobs = {}
    for i, keyword in enumerate(keywords):
        if i > 0:
            time.sleep(common.REQUEST_DELAY_SECONDS)
        try:
            html = fetch_search_html(keyword)
        except Exception as e:
            print(f"关键词「{keyword}」抓取失败，跳过：{e}")
            continue
        for job in parse_job_cards(html, keyword):
            all_jobs[job["id"]] = job

    # 第二步：给每个职位补上详情页信息（真实名称、转正机会、薪资）
    excluded_count = 0
    kept_jobs = {}
    for job_id, job in all_jobs.items():
        time.sleep(common.REQUEST_DELAY_SECONDS)
        try:
            detail = fetch_job_detail(job_id)
        except Exception:
            detail = {"title": None, "chance": None, "offers_fulltime": False, "salary": None}
        job.update(detail)

        if common.is_excluded(job["title"]):
            excluded_count += 1
            continue
        if common.salary_too_low(job["salary"]):
            excluded_count += 1
            continue
        kept_jobs[job_id] = job

    return common.mark_new_and_save(kept_jobs, OUTPUT_FILE, excluded_count)


if __name__ == "__main__":
    result = run(common.SEARCH_KEYWORDS)
    print(f"抓到 {result['job_count']} 个职位，已保存到 {OUTPUT_FILE}")
    print(f"过滤掉剧组类岗位 {result['excluded_count']} 个")
    new_count = sum(1 for j in result["jobs"] if j["is_new"])
    fulltime_count = sum(1 for j in result["jobs"] if j["offers_fulltime"])
    print(f"其中「新职位」有 {new_count} 个，「提供转正」的有 {fulltime_count} 个")
