"""
Moka 招聘平台抓取脚本 —— 一次性覆盖几十家中厂的官网校招

很多中厂不自己开发招聘系统，而是买了「Moka」这个第三方招聘平台来搭建自己的
招聘官网（比如你在 app.mokahr.com 上看到的各家校招页面，其实都是同一套系统）。
所以只要打通 Moka，就等于同时打通了下面这一长串公司的官网校招。

这个平台把返回的数据做了一层加密（不是登录保护，页面本身谁都能公开浏览，
只是防止程序直接读取）。解密需要两把钥匙，都能公开拿到：
  - 钥匙一：跟数据一起返回的 necromancer 字段
  - 钥匙二：写在网页源码里的 aesIv
拿到这两个就能还原成正常的岗位数据。

另外这个平台有个很方便的特性：只要知道公司代号（比如月之暗面是 moonshot），
访问不带站点编号的网址会自动跳转到该公司当前的校招站点。所以下面的公司列表
只需要维护公司代号，不用手动去找站点编号。
"""

from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

import common
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
OUTPUT_FILE = DATA_DIR / "jobs_moka.json"

DEFAULT_BASE = "https://app.mokahr.com"

# 要抓的公司列表。想加公司，只要在这里加一行公司代号就行。
# 公司代号怎么找：打开这家公司的校招网页，看网址里 campus-recruitment/ 后面那一段。
# 有的公司用自己的域名（比如芒果TV），就额外写上 base。
COMPANIES = [
    # —— AI 方向的中厂 ——
    {"name": "月之暗面(Kimi)", "org": "moonshot"},
    {"name": "阶跃星辰", "org": "step"},
    {"name": "面壁智能", "org": "modelbest"},
    {"name": "第四范式", "org": "4paradigm"},
    {"name": "昆仑万维", "org": "kunlun"},
    {"name": "云从科技", "org": "cloudwalk"},
    {"name": "涂鸦智能", "org": "tuya"},
    {"name": "声网Agora", "org": "agora"},
    # —— 内容 / 社区 / 影像方向的中厂 ——
    {"name": "知乎", "org": "zhihu"},
    {"name": "美图", "org": "meitu"},
    {"name": "阅文集团", "org": "yuewen"},
    {"name": "影石Insta360", "org": "insta360"},
    {"name": "斗鱼", "org": "douyu"},
    {"name": "虎牙", "org": "huya"},
    {"name": "芒果TV", "org": "mgtv", "base": "https://hr.mgtv.com"},
    # —— 游戏 / 泛娱乐中厂（美术、文案、宣发类岗位多）——
    {"name": "鹰角网络", "org": "hypergryph"},
    {"name": "盛趣游戏", "org": "shengqu"},
    {"name": "游族网络", "org": "yoozoo"},
    {"name": "三七互娱", "org": "37"},
    {"name": "莉莉丝游戏", "org": "lilith"},
    {"name": "紫龙游戏", "org": "zlongame"},
    {"name": "恺英网络", "org": "kingnet"},
    {"name": "心动网络", "org": "xd"},
    {"name": "雷霆游戏", "org": "leiting"},
    # —— 媒体 / 资讯类中厂 ——
    {"name": "搜狐", "org": "sohu"},
    {"name": "新浪", "org": "sina"},
    {"name": "凤凰网", "org": "ifeng"},
    {"name": "虎嗅", "org": "huxiu"},
    {"name": "爱奇艺", "org": "iqiyi"},
    # —— 其他 ——
    {"name": "金山办公WPS", "org": "wps"},
    {"name": "作业帮", "org": "zuoyebang"},
    {"name": "SHEIN", "org": "shein"},
    {"name": "滴滴", "org": "didiglobal"},
    {"name": "途虎养车", "org": "tuhu"},
    {"name": "大华股份", "org": "dahua"},
    {"name": "58同城", "org": "58"},
    {"name": "贝壳找房", "org": "ke"},
    {"name": "去哪儿", "org": "qunar"},
    {"name": "李宁", "org": "lining"},
    {"name": "太平鸟", "org": "peacebird"},
    {"name": "寒武纪", "org": "cambricon"},
]

# 岗位标题里出现这些词才保留（传媒 + AI 两个方向的词根）
KEEP_TITLE_KEYWORDS = [
    # 传媒方向
    "新媒体", "短视频", "视频", "剪辑", "摄影", "摄像", "直播", "内容",
    "文案", "短剧", "编导", "制片", "策划", "运营", "宣发", "分镜",
    "创意", "美术", "动效", "设计", "编剧", "主播", "社媒", "品牌",
    # AI 方向（你说沾点边就行，所以这里放得比较宽）
    "AI", "AIGC", "人工智能", "大模型", "多模态", "生成式", "标注",
    "Agent", "Kimi", "提示词", "Prompt",
]

# 但如果标题里有这些词，说明是要写代码/做硬件的技术岗，你的专业投不了，排除掉
EXCLUDE_TECH_KEYWORDS = [
    "算法工程师", "开发工程师", "研发工程师", "后端", "前端", "客户端",
    "全栈", "架构", "嵌入式", "硬件", "驱动", "编译", "测试开发",
    "运维", "C++", "Java", "服务端", "数据仓库", "数仓", "SRE",
]


def _new_session():
    import requests

    s = requests.Session()
    s.headers.update(common.HEADERS)
    return s


def discover_site_id(session, org: str, base: str) -> int | None:
    """只给公司代号，让网站自己告诉我们当前的校招站点编号"""
    r = session.get(f"{base}/campus-recruitment/{org}/", timeout=25, allow_redirects=True)
    m = re.search(rf"/campus-recruitment/{re.escape(org)}/(\d+)", r.url)
    return int(m.group(1)) if m else None


def _get_aes_iv(session, page_url: str) -> str | None:
    """从网页源码里取出解密用的第二把钥匙"""
    page = session.get(page_url, timeout=25)
    m = re.search(r"aesIv&quot;:&quot;([a-f0-9]+)&quot;", page.text) or re.search(
        r'aesIv":"([a-f0-9]+)"', page.text
    )
    return m.group(1) if m else None


def _decrypt(resp: dict, aes_iv: str) -> dict:
    """用两把钥匙把加密的数据还原成正常内容"""
    key = resp["necromancer"].encode()
    cipher = AES.new(key, AES.MODE_CBC, aes_iv.encode())
    plain = unpad(cipher.decrypt(base64.b64decode(resp["data"])), AES.block_size)
    return json.loads(plain.decode("utf-8"))


def fetch_jobs(session, org: str, site_id: int, base: str, max_pages: int = 8) -> list[dict]:
    """把一家公司校招站点上的岗位一页页取下来

    翻页靠的是 offset（已经取了多少条），每页最多 50 条。
    """
    page_url = f"{base}/campus-recruitment/{org}/{site_id}"
    aes_iv = _get_aes_iv(session, page_url)

    limit = 50
    all_jobs = []
    for page_no in range(max_pages):
        if page_no > 0:
            time.sleep(common.REQUEST_DELAY_SECONDS)
        r = session.post(
            f"{base}/api/outer/ats-apply/website/jobs/v2",
            json={
                "orgId": org,
                "siteId": site_id,
                "keyword": "",
                "offset": page_no * limit,
                "limit": limit,
                "locale": "zh-CN",
            },
            headers={"Referer": page_url, "Content-Type": "application/json"},
            timeout=25,
        )
        resp = r.json()
        if "necromancer" in resp:
            if not aes_iv:
                break
            resp = _decrypt(resp, aes_iv)
        jobs = (resp.get("data") or {}).get("jobs") or []
        all_jobs.extend(jobs)
        if len(jobs) < limit:
            break  # 已经是最后一页了
    return all_jobs


def is_wanted(title: str) -> bool:
    """判断这个岗位标题是不是你会感兴趣的方向"""
    if not title:
        return False
    if any(kw in title for kw in EXCLUDE_TECH_KEYWORDS):
        return False
    return any(kw in title for kw in KEEP_TITLE_KEYWORDS)


def _strip_html(text: str | None) -> str:
    """岗位描述是带网页标签的，这里把标签去掉只留纯文字"""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text)


# 直辖市：这几个地方返回的"城市"其实是区名（比如海淀区），
# 显示成"北京"更好懂，筛选的时候也不会被拆成一堆区
MUNICIPALITIES = ("北京", "上海", "天津", "重庆")


def _city_of(post: dict) -> str | None:
    """从岗位信息里取出工作城市（可能有多个）"""
    locations = post.get("locations") or []
    names = []
    for loc in locations:
        province = (loc.get("provinceName") or "").rstrip("市")
        city = (loc.get("cityName") or "").rstrip("市")
        # 直辖市用省级名字（北京），其他地方用城市名（杭州）
        name = province if province in MUNICIPALITIES else (city or province)
        if name and name not in names:
            names.append(name)
    return "/".join(names) if names else None


def to_job_dict(post: dict, company_name: str, org: str, site_id: int, base: str) -> dict:
    title = post.get("title")
    commitment = post.get("commitment")  # 全职 / 实习
    department = (post.get("department") or {}).get("name")
    description = _strip_html(post.get("jobDescription"))

    # 判断是否属于"秋招可转正"这一档。这些岗位本来就都来自各公司的
    # 「校园招聘」站点，所以只要满足下面任意一条就归到这一档：
    # 1) 标题里明写了转正 / 留用 / 提前批
    # 2) 标题里带届别或"秋招"字样，同时又是实习岗
    #    （比如"27届Stepstar实习""2027届秋招-文案策划"）
    title_text = title or ""
    is_intern = "实习" in title_text or commitment == "实习"
    has_campus_marker = bool(re.search(r"(20)?2[5-9]\s*届", title_text)) or "秋招" in title_text
    offers_fulltime = common.looks_like_fulltime_track(title_text, description) or (
        has_campus_marker and is_intern
    )

    published = post.get("publishedAt") or post.get("openedAt") or post.get("createdAt")
    publish_date = published.replace("T", " ") if published else None

    tags = [t for t in [commitment, department] if t]

    return {
        "id": f"moka_{org}_{post.get('id')}",
        "title": title,
        "company": company_name,
        "city": _city_of(post),
        "industry": department,
        "tags": tags,
        # 注意网址里的 # 号不能少，这是这类网页跳转到具体职位的写法，
        # 少了它会打开"页面不存在"
        "link": f"{base}/campus-recruitment/{org}/{site_id}#/job/{post.get('id')}",
        "search_keyword": None,
        "source": f"{company_name}官网",
        "publish_date": publish_date,
        "salary": None,
        "offers_fulltime": offers_fulltime,
        # 这一条标记说明岗位直接来自公司自己的「校园招聘」官网
        "is_campus_official": True,
    }


def run(companies: list[dict]) -> dict:
    session = _new_session()
    all_jobs = {}
    excluded_count = 0

    for i, comp in enumerate(companies):
        if i > 0:
            time.sleep(common.REQUEST_DELAY_SECONDS)

        name, org = comp["name"], comp["org"]
        base = comp.get("base", DEFAULT_BASE)

        try:
            site_id = comp.get("site_id") or discover_site_id(session, org, base)
            if not site_id:
                print(f"{name}：没找到校招站点，跳过")
                continue
            posts = fetch_jobs(session, org, site_id, base)
        except Exception as e:
            print(f"{name}：抓取失败，跳过（{e}）")
            continue

        kept = 0
        for post in posts:
            title = post.get("title") or ""
            # 状态不是 open 的（比如已暂停招聘）就不要了，免得白高兴一场
            if post.get("status") != "open":
                continue
            if not is_wanted(title):
                continue
            if common.is_excluded(title):
                excluded_count += 1
                continue
            job = to_job_dict(post, name, org, site_id, base)
            all_jobs[job["id"]] = job
            kept += 1

        print(f"{name}：共 {len(posts)} 个岗位，符合你方向的 {kept} 个")

    return common.mark_new_and_save(all_jobs, OUTPUT_FILE, excluded_count)


if __name__ == "__main__":
    result = run(COMPANIES)
    print(f"\n合计抓到 {result['job_count']} 个职位，已保存到 {OUTPUT_FILE}")
    new_count = sum(1 for j in result["jobs"] if j["is_new"])
    fulltime_count = sum(1 for j in result["jobs"] if j["offers_fulltime"])
    print(f"其中「新职位」{new_count} 个，判定为「秋招可转正」的 {fulltime_count} 个")
