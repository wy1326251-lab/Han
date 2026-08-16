// 这里列出所有数据来源文件。以后新增抓取来源（比如字节跳动、腾讯官网）时，
// 只需要把生成的 JSON 文件路径加到这个数组里，网页就会自动把它们合并展示。
const DATA_SOURCES = [
  "data/jobs_shixiseng.json",
  "data/jobs_tencent.json",
  "data/jobs_kuaishou.json",
  "data/jobs_netease.json",
  "data/jobs_moka.json",
];

let allJobs = [];

// 大厂名单：几乎人人都听说过的头部公司
// 想增删公司，改这两个列表就行，不用动别的代码。
const TOP_COMPANIES = [
  "字节跳动", "抖音", "西瓜视频", "腾讯", "阿里巴巴", "阿里", "百度", "美团",
  "京东", "快手", "哔哩哔哩", "B站", "网易", "小米", "拼多多", "华为",
  "携程", "滴滴", "OPPO", "vivo",
];

// 中厂名单：在各自领域里比较知名，但没有大厂那么"人尽皆知"
const MID_COMPANIES = [
  "爱奇艺", "优酷", "芒果TV", "芒果超媒", "微博", "知乎", "得物",
  "小红书", "喜马拉雅", "360", "搜狐", "搜狗", "唯品会", "饿了么", "高德",
  "猿辅导", "作业帮", "好未来", "新东方", "完美世界", "三七互娱", "米哈游",
  "莉莉丝", "叠纸", "腾讯音乐", "网易云音乐", "虎牙", "斗鱼", "陌陌",
  "汽车之家", "贝壳", "顺丰",
  // AI 方向的中厂
  "月之暗面", "Kimi", "阶跃星辰", "面壁智能", "第四范式", "昆仑万维",
  "云从", "涂鸦智能", "声网", "智谱", "MiniMax", "商汤", "旷视", "科大讯飞",
  // 内容 / 影像 / 游戏方向的中厂
  "美图", "阅文", "影石", "Insta360", "鹰角", "盛趣", "游族",
  "金山", "WPS", "快看", "掌阅", "B站",
  "紫龙", "恺英", "心动", "雷霆", "新浪", "凤凰网", "虎嗅",
  "58同城", "去哪儿", "李宁", "太平鸟", "寒武纪",
  "SHEIN", "途虎", "大华",
];

// 四个档位：1=秋招可转正实习（最高），2=大厂日常实习，3=中厂日常实习，4=普通日常实习
const TIER_INFO = {
  1: { label: "秋招可转正", className: "tier-1" },
  2: { label: "大厂实习", className: "tier-2" },
  3: { label: "中厂实习", className: "tier-3" },
  4: { label: "普通实习", className: "tier-4" },
};

function getTier(job) {
  if (job.offers_fulltime) return 1;
  const company = job.company || "";
  if (TOP_COMPANIES.some((c) => company.includes(c))) return 2;
  if (MID_COMPANIES.some((c) => company.includes(c))) return 3;
  return 4;
}

// ===== 城市名统一 =====
//
// 各个招聘网站写城市的方式五花八门：有的写"北京"，有的写"北京市"，
// 有的干脆写成区名（"番禺区""南山区"），还有的写"合肥高新技术产业开发区"。
// 不统一的话，同一个城市会在筛选框里出现好几次，用起来很乱。
// 下面这些代码就是把它们都归到同一个名字上。

// 区名 → 所属城市
const DISTRICT_TO_CITY = {
  // 北京
  东城区: "北京", 西城区: "北京", 朝阳区: "北京", 海淀区: "北京",
  丰台区: "北京", 石景山区: "北京", 门头沟区: "北京", 房山区: "北京",
  通州区: "北京", 顺义区: "北京", 昌平区: "北京", 大兴区: "北京",
  怀柔区: "北京", 平谷区: "北京", 密云区: "北京", 延庆区: "北京",
  // 上海
  黄浦区: "上海", 徐汇区: "上海", 长宁区: "上海", 静安区: "上海",
  普陀区: "上海", 虹口区: "上海", 杨浦区: "上海", 闵行区: "上海",
  宝山区: "上海", 嘉定区: "上海", 浦东新区: "上海", 金山区: "上海",
  松江区: "上海", 青浦区: "上海", 奉贤区: "上海", 崇明区: "上海",
  // 广州
  越秀区: "广州", 海珠区: "广州", 荔湾区: "广州", 天河区: "广州",
  白云区: "广州", 黄埔区: "广州", 番禺区: "广州", 花都区: "广州",
  南沙区: "广州", 从化区: "广州", 增城区: "广州",
  // 深圳
  福田区: "深圳", 罗湖区: "深圳", 南山区: "深圳", 宝安区: "深圳",
  龙岗区: "深圳", 龙华区: "深圳", 坪山区: "深圳", 光明区: "深圳",
  盐田区: "深圳",
  // 杭州
  上城区: "杭州", 拱墅区: "杭州", 西湖区: "杭州", 滨江区: "杭州",
  萧山区: "杭州", 余杭区: "杭州", 富阳区: "杭州", 临平区: "杭州",
  钱塘区: "杭州",
  // 成都
  锦江区: "成都", 青羊区: "成都", 金牛区: "成都", 武侯区: "成都",
  成华区: "成都", 龙泉驿区: "成都", 双流区: "成都", 郫都区: "成都",
  // 南京
  玄武区: "南京", 秦淮区: "南京", 建邺区: "南京", 鼓楼区: "南京",
  栖霞区: "南京", 雨花台区: "南京", 江宁区: "南京", 浦口区: "南京",
  // 武汉
  江岸区: "武汉", 江汉区: "武汉", 硚口区: "武汉", 汉阳区: "武汉",
  武昌区: "武汉", 青山区: "武汉", 洪山区: "武汉", 东西湖区: "武汉",
  // 西安
  新城区: "西安", 碑林区: "西安", 莲湖区: "西安", 雁塔区: "西安",
  未央区: "西安", 长安区: "西安",
  // 其他
  香洲区: "珠海", 金湾区: "珠海", 姑苏区: "苏州", 工业园区: "苏州",
  思明区: "厦门", 湖里区: "厦门", 渝中区: "重庆", 江北区: "重庆",
};

function normalizeCityName(raw) {
  if (!raw) return null;
  let name = raw.trim();
  if (!name) return null;

  // "合肥高新技术产业开发区" 这类，取前面的城市名
  const devZone = name.match(
    /^(.+?)(高新技术产业开发区|经济技术开发区|经济开发区|高新区|开发区)$/
  );
  if (devZone && devZone[1]) name = devZone[1];

  if (DISTRICT_TO_CITY[name]) return DISTRICT_TO_CITY[name];

  // 去掉结尾的"市"，让"北京市"和"北京"合并成一个
  if (name.length > 2 && name.endsWith("市")) name = name.slice(0, -1);

  return DISTRICT_TO_CITY[name] || name;
}

// 一个岗位可能挂着多个城市（"北京/上海"），这里拆开、规整、去重。
// 排过序之后，"北京/上海"和"上海/北京"就会变成同一个东西。
function cityListOf(rawCity) {
  if (!rawCity) return [];
  const out = [];
  for (const part of String(rawCity).split("/")) {
    const name = normalizeCityName(part);
    if (name && !out.includes(name)) out.push(name);
  }
  return out.sort();
}

// 数据文件里存的更新时间是北京时间（抓取脚本那边已经统一转换过了），
// 这里假设你也是在中国时区看这个网页，所以直接用浏览器本地日期来比较，
// 不用再额外做时区换算。
function showFreshnessDot(latestUpdate) {
  const dot = document.getElementById("freshnessDot");
  if (!latestUpdate) {
    dot.hidden = true;
    return;
  }

  const updatedDatePart = latestUpdate.slice(0, 10); // "YYYY-MM-DD"
  const now = new Date();
  const todayPart = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");

  const isFresh = updatedDatePart === todayPart;
  dot.hidden = false;
  dot.className = "freshness-dot " + (isFresh ? "fresh" : "stale");
  dot.title = isFresh
    ? "今天已经自动更新过了"
    : "今天还没更新——可能是还没到自动抓取的时间，也可能是抓取遇到了问题";
}

async function loadData() {
  const results = await Promise.all(
    DATA_SOURCES.map((url) =>
      fetch(url)
        .then((r) => r.json())
        .catch(() => null)
    )
  );

  const validResults = results.filter(Boolean);
  allJobs = validResults.flatMap((r) => r.jobs || []);

  // 先把每个岗位的城市规整好存起来，后面筛选和显示都直接用，
  // 不用每次都重新算一遍
  allJobs.forEach((job) => {
    job.cities = cityListOf(job.city);
    job.cityText = job.cities.join(" / ");
  });

  const latestUpdate = validResults
    .map((r) => r.updated_at)
    .filter(Boolean)
    .sort()
    .pop();

  document.getElementById("updateInfo").textContent = latestUpdate
    ? `最近更新时间：${latestUpdate} ｜ 共 ${allJobs.length} 个职位`
    : "暂无数据";

  showFreshnessDot(latestUpdate);

  populateFilterOptions();
  render();
}

function populateFilterOptions() {
  // 统计每个城市有多少个岗位。一个挂着"北京/上海"的岗位，
  // 在北京和上海下面各算一次，这样选哪个都能找到它。
  const cityCount = new Map();
  allJobs.forEach((job) => {
    job.cities.forEach((c) => cityCount.set(c, (cityCount.get(c) || 0) + 1));
  });

  // 岗位多的城市排前面，省得每次都要在长长的列表里翻找北京、上海
  const cities = [...cityCount.entries()].sort((a, b) => b[1] - a[1]);

  const companies = [...new Set(allJobs.map((j) => j.company).filter(Boolean))].sort();

  const citySelect = document.getElementById("citySelect");
  cities.forEach(([city, count]) => {
    const opt = document.createElement("option");
    opt.value = city;
    opt.textContent = `${city}（${count}）`;
    citySelect.appendChild(opt);
  });

  const companySelect = document.getElementById("companySelect");
  companies.forEach((company) => {
    const opt = document.createElement("option");
    opt.value = company;
    opt.textContent = company;
    companySelect.appendChild(opt);
  });
}

function jobHeadline(job) {
  if (job.title) return job.title;
  const parts = [job.search_keyword, job.industry].filter(Boolean);
  return parts.length ? `${parts.join(" · ")} 实习` : "实习职位";
}

function matchesFilters(job, keyword, city, company, newOnly, tier, officialOnly) {
  // 一个岗位可能在多个城市招人，只要包含你选的那个就算匹配
  if (city && !job.cities.includes(city)) return false;
  if (company && job.company !== company) return false;
  if (newOnly && !job.is_new) return false;
  if (officialOnly && !job.is_campus_official) return false;
  if (tier && getTier(job) !== Number(tier)) return false;

  if (keyword) {
    const haystack = [
      job.title,
      job.company,
      job.city,
      job.cityText,
      job.industry,
      job.search_keyword,
      ...(job.tags || []),
    ]
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(keyword.toLowerCase())) return false;
  }

  return true;
}

function render() {
  const keyword = document.getElementById("searchInput").value.trim();
  const city = document.getElementById("citySelect").value;
  const company = document.getElementById("companySelect").value;
  const newOnly = document.getElementById("newOnlyCheckbox").checked;
  const officialOnly = document.getElementById("officialOnlyCheckbox").checked;
  const tier = document.getElementById("tierSelect").value;

  const filtered = allJobs
    .filter((job) =>
      matchesFilters(job, keyword, city, company, newOnly, tier, officialOnly)
    )
    .sort((a, b) => {
      if (a.is_new !== b.is_new) return a.is_new ? -1 : 1;
      const tierDiff = getTier(a) - getTier(b);
      if (tierDiff !== 0) return tierDiff;
      return (b.first_seen || "").localeCompare(a.first_seen || "");
    });

  const listEl = document.getElementById("jobList");
  const emptyEl = document.getElementById("emptyMessage");
  const countEl = document.getElementById("resultCount");

  countEl.textContent = `显示 ${filtered.length} / ${allJobs.length} 个职位`;
  listEl.innerHTML = "";

  if (filtered.length === 0) {
    emptyEl.hidden = false;
    return;
  }
  emptyEl.hidden = true;

  for (const job of filtered) {
    const tier = getTier(job);
    const tierInfo = TIER_INFO[tier];

    const card = document.createElement("a");
    card.className = `job-card ${tierInfo.className}`;
    card.href = job.link;
    card.target = "_blank";
    card.rel = "noopener noreferrer";

    const top = document.createElement("div");
    top.className = "job-card-top";

    const tierBadge = document.createElement("span");
    tierBadge.className = `tier-badge ${tierInfo.className}`;
    tierBadge.textContent = tierInfo.label;
    top.appendChild(tierBadge);

    const title = document.createElement("span");
    title.className = "job-title";
    title.textContent = jobHeadline(job);
    top.appendChild(title);

    if (job.is_new) {
      const badge = document.createElement("span");
      badge.className = "new-badge";
      badge.textContent = "NEW";
      top.appendChild(badge);
    }

    if (job.is_campus_official) {
      const badge = document.createElement("span");
      badge.className = "official-badge";
      badge.textContent = "官网校招";
      top.appendChild(badge);
    }

    const meta = document.createElement("div");
    meta.className = "job-meta";
    const metaParts = [
      `<span class="company">${job.company || "未知公司"}</span>`,
      job.cityText || "地点未知",
      job.salary || "",
      job.publish_date ? `发布于 ${job.publish_date}` : "",
      job.source || "",
    ].filter(Boolean);
    meta.innerHTML = metaParts.join(" · ");

    const tagRow = document.createElement("div");
    tagRow.className = "tag-row";
    (job.tags || []).forEach((t) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = t;
      tagRow.appendChild(tag);
    });

    card.appendChild(top);
    card.appendChild(meta);
    card.appendChild(tagRow);
    listEl.appendChild(card);
  }
}

// ===== 白天 / 夜间 主题切换 =====
//
// 一共有三种状态：
//   1. 你没做过选择 —— 跟着手机/电脑的系统设置走（系统深色，网页就深色）
//   2. 你手动选了夜间 —— 一直深色
//   3. 你手动选了白天 —— 一直浅色
// 你的选择会记在这台设备的浏览器里，下次打开还是你选的那个。

const themeToggle = document.getElementById("themeToggle");

function currentlyDark() {
  const saved = document.documentElement.getAttribute("data-theme");
  if (saved === "dark") return true;
  if (saved === "light") return false;
  // 没手动选过，就看系统是不是深色
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function updateToggleLabel() {
  // 按钮上显示的是"点了之后会变成什么"，而不是"现在是什么"
  themeToggle.textContent = currentlyDark() ? "☀️ 白天" : "🌙 夜间";
}

themeToggle.addEventListener("click", () => {
  const next = currentlyDark() ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  updateToggleLabel();
});

// 如果你没手动选过，而系统主题变了（比如到了晚上自动切深色），
// 网页要跟着变，按钮文字也要跟着更新
window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", () => {
    if (!document.documentElement.hasAttribute("data-theme")) {
      updateToggleLabel();
    }
  });

updateToggleLabel();

// ===== 筛选控件 =====
document.getElementById("searchInput").addEventListener("input", render);
document.getElementById("citySelect").addEventListener("change", render);
document.getElementById("companySelect").addEventListener("change", render);
document.getElementById("tierSelect").addEventListener("change", render);
document.getElementById("newOnlyCheckbox").addEventListener("change", render);
document.getElementById("officialOnlyCheckbox").addEventListener("change", render);

loadData();
