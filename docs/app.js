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

  const latestUpdate = validResults
    .map((r) => r.updated_at)
    .filter(Boolean)
    .sort()
    .pop();

  document.getElementById("updateInfo").textContent = latestUpdate
    ? `最近更新时间：${latestUpdate} ｜ 共 ${allJobs.length} 个职位`
    : "暂无数据";

  populateFilterOptions();
  render();
}

function populateFilterOptions() {
  const cities = [...new Set(allJobs.map((j) => j.city).filter(Boolean))].sort();
  const companies = [...new Set(allJobs.map((j) => j.company).filter(Boolean))].sort();

  const citySelect = document.getElementById("citySelect");
  cities.forEach((city) => {
    const opt = document.createElement("option");
    opt.value = city;
    opt.textContent = city;
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
  if (city && job.city !== city) return false;
  if (company && job.company !== company) return false;
  if (newOnly && !job.is_new) return false;
  if (officialOnly && !job.is_campus_official) return false;
  if (tier && getTier(job) !== Number(tier)) return false;

  if (keyword) {
    const haystack = [
      job.title,
      job.company,
      job.city,
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
      job.city || "地点未知",
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

document.getElementById("searchInput").addEventListener("input", render);
document.getElementById("citySelect").addEventListener("change", render);
document.getElementById("companySelect").addEventListener("change", render);
document.getElementById("tierSelect").addEventListener("change", render);
document.getElementById("newOnlyCheckbox").addEventListener("change", render);
document.getElementById("officialOnlyCheckbox").addEventListener("change", render);

loadData();
