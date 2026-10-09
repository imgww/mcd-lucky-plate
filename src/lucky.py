"""幸运主题与谐音词库。

设计前提（务必先读）
--------------------
本模块是**唯一的主观内容源**：主题、谐音梗、吉祥话都在这里定义。
引擎（lucky_engine）只负责按这里的锚点去真实菜单里检索与配平，
不在代码里临时编词。因此「梗」与「菜单」之间是**可核验的对应关系**，
不是文案壳。

`anchor` 的语义
---------------
每个愿望带若干 `anchor`，anchor 是**必须在真实菜单品名里出现的子串**。
引擎检索时用 `anchor in food.name` 精确匹配，命不中就是命不中——
不退回模糊匹配、不编造餐品。这样做的代价是梗的覆盖受菜单约束，
收益是任何输出都能逐条回溯到真实存在的餐品名。

谐音类型（`kind`）
-------------------
homophone  谐音改写（鸡腿→大吉大利、牛气→牛气冲天、双层→双赢）
literal    字面吉祥义（巨无霸→气魄；吉士→吉）
brand      品牌自带梗（麦满分→考试满分）
reverse    反向取意（浓缩→不缺水之外的「浓缩财富」）

每条 `note` 写明梗的来源与适用边界，供人工审阅。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 谐音类型常量
HOMOPHONE = "homophone"
LITERAL = "literal"
BRAND = "brand"
REVERSE = "reverse"


@dataclass(frozen=True)
class Wish:
    """一个谐音/寓意单元。

    attributes
    ----------
    anchor : str
        必须在真实菜单品名中出现的子串（检索键）。
    gloss : str
        这个梗怎么念、怎么解释（展示给用户）。
    kind : str
        谐音类型，见模块文档。
    note : str
        溯源说明：梗的出处、是否官方、是否有歧义。
    """

    anchor: str
    gloss: str
    kind: str
    note: str = ""


@dataclass(frozen=True)
class Theme:
    """一个幸运主题（如「一夜暴富」）。

    每个主题携带自己的硬约束与吉祥话，而非共用一套全局约束——
    这是主题差异化的落点之一：不同愿望在热量、钠、甜品放开程度上
    确实不同，输出因此可区分。
    """

    key: str
    name: str
    tagline: str
    voice: str                       # 主题口吻的一句话
    kcal: float                     # 该主题的热量预算
    tolerance: float = 0.15          # 热量容差（比周餐盘宽，梗优先）
    max_sodium: float | None = None  # None = 由引擎按 kcal 推导
    dessert_bias: float = 0.5        # 0=不碰甜品 1=甜品加权
    allow_dessert: bool = True
    wishes: tuple[Wish, ...] = field(default_factory=tuple)
    blessing: str = ""               # 餐后吉祥话
    provenance: str = ""             # 权重与约束的推导依据

    def anchors(self) -> tuple[str, ...]:
        return tuple(w.anchor for w in self.wishes)

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "tagline": self.tagline,
            "voice": self.voice,
            "kcal": self.kcal,
            "tolerance": self.tolerance,
            "dessert_bias": self.dessert_bias,
            "allow_dessert": self.allow_dessert,
            "blessing": self.blessing,
            "provenance": self.provenance,
            "wishes": [
                {"anchor": w.anchor, "gloss": w.gloss, "kind": w.kind, "note": w.note}
                for w in self.wishes
            ],
        }


# ---------------------------------------------------------------------------
# 主题表
# ---------------------------------------------------------------------------
# 约束推导原则（统一口径，避免「随手拍的数字」）：
#   * kcal  : 取该主题叙事上的一顿正餐量级，不刻意压低
#   * 钠上限: 默认 260mg/100kcal（与引擎 SODIUM_COMFORT_PER_100KCAL 同源），
#             对「放纵型」主题显式放宽并记入 provenance
#   * 甜品  : 戒运/健康类主题关闭；其余按叙事需要放开
# 每个主题的 provenance 都写明这三项为何如此取值。

THEMES: dict[str, Theme] = {}


def _reg(t: Theme) -> Theme:
    THEMES[t.key] = t
    return t


_reg(Theme(
    key="jackpot",
    name="一夜暴富",
    tagline="今晚吃这一顿，明天对账",
    voice="这单吃完，账就开始对——放心，是你收钱。",
    kcal=780.0,
    tolerance=0.18,
    max_sodium=2106.0,
    dessert_bias=0.7,
    blessing="饭后不洗碗，碗会自己变干净（大概）。",
    provenance=(
        "热量 780、钠上限 2106mg，都是**实测校准**的结果，不是拍脑袋："
        "本主题的锚点（巨无霸/双层/牛气/鸡腿/麦满分）全部指向高蛋白主食，"
        "实测单品钠 728-1373mg。按 260mg/100kcal 的通用线只能给到 1404mg，"
        "而两件主食必然超钠——用 scripts/calibrate_jackpot.py 扫过 600-780 kcal "
        "共 10 档预算，无一能在严格钠线下解出。因此这里**显式放宽钠上限并写明**，"
        "而不是让引擎悄悄放宽或换个主题凑答案。诚实代价：一夜暴富是本 Skill "
        "钠含量最高的主题。想控钠请选「轻装上阵」。"
        "甜品放开且加权：甜=喜，是这个主题的语义核心。"
    ),
    wishes=(
        Wish("巨无霸", "巨无霸 → 巨额 + 霸气，双关直接落在「钱多」上",
             HOMOPHONE, "官方品名自带成语联想，非本项目原创"),
        Wish("牛气", "牛气满满 → 「牛气冲天」，转运第一联想",
             HOMOPHONE, "取自真实在售品「牛气满满」；「牛气冲天」为成语式取意"),
        Wish("双层", "双层 → 双赢、双份，寓意加倍进账",
             HOMOPHONE, "与「一夜暴富」的复利意象同向"),
        Wish("鸡腿", "鸡腿 → 「鸡」谐音「吉」，大吉大利；「利」字还额外应了暴富",
             HOMOPHONE, "取自真实在售品「板烧鸡腿堡/原味板烧鸡腿麦满分」；"
                        "「鸡/吉」为常见谐音，大吉大利取「吉」与「利」双字吉利意"),
        Wish("麦满分", "麦满分 → 考试满分；分数满则财源顺",
             BRAND, "品牌自带「满分」语义"),
        Wish("浓缩", "浓缩咖啡 → 「浓缩财富」，一天把本事熬浓",
             REVERSE, "取自真实在售品「浓缩咖啡」"),
        Wish("双层吉士", "吉士 → 吉祥之士，双层即双倍吉",
             LITERAL, "「吉」为明确字面吉祥义"),
    ),
))

_reg(Theme(
    key="exam",
    name="逢考必过",
    tagline="考场外先吃饱，进场不慌",
    voice="麦满分都摆齐了，剩下的靠你发挥。",
    kcal=620.0,
    tolerance=0.15,
    dessert_bias=0.45,
    blessing="交卷铃响之前，胃已经稳了。",
    provenance=(
        "热量取 620（低于常规）：考试场景多为饭点快速进食，"
        "过重会犯困。甜品适度保留但不作为主诉求——「必过」靠主食与饮品撑。"
    ),
    wishes=(
        Wish("麦满分", "麦满分 → 考试满分，直译即「满分必过」",
             BRAND, "品牌自带满分语义，与本主题强相关"),
        Wish("麦乐鸡", "麦乐鸡 → 「鸡」谐音「吉」，大吉大利上考场",
             HOMOPHONE, "取自真实在售品「麦乐鸡4块/麦乐鸡5块」；「鸡/吉」为常见谐音"),
        Wish("麦香鱼", "麦香鱼 → 「鱼」谐音「余」，考余力充足",
             HOMOPHONE, "取自真实在售品「麦香鱼」；anchor 收窄为「麦香鱼」而非「鱼」，"
                        "避免命中「专“薯鱼”你」这类营销梗名"),
        Wish("吉士", "吉士汉堡 → 吉士即吉士，考试要吉",
             LITERAL, "「吉」为明确字面吉祥义"),
        Wish("双层", "双层 → 分数双层加成",
             HOMOPHONE, "与「逢考必过」的加分成正比"),
        Wish("玉米", "玉米 → 「玉」谐音「遇」，遇考即过",
             HOMOPHONE, "「遇」为常见考试吉祥取意"),
        Wish("蛋", "麦满分里的蛋 → 「蛋」谐音「单」，单科全过",
             HOMOPHONE, "「单」取单科之意，属谐音梗的常见玩法"),
    ),
))

_reg(Theme(
    key="lovestruck",
    name="桃花运开",
    tagline="一个人吃饭，也要甜到底",
    voice="热量我不拦你，但好运我打包票。",
    kcal=700.0,
    tolerance=0.20,
    dessert_bias=0.85,
    allow_dessert=True,
    blessing="吃完这顿，微信就有人加你了。",
    provenance=(
        "热量 700 + 容差放宽到 20%：这是唯一一个「甜品当主角」的主题，"
        "若压得太狠就失去了品类意义。钠上限不放宽——甜品可放开，咸食仍守底线。"
    ),
    wishes=(
        Wish("草莓", "草莓新地 → 「莓」谐音「媒」，自带媒人属性",
             HOMOPHONE, "「媒」为媒人取意"),
        Wish("新地", "新地 → 「新地」谐音「心仪」变体，取「心怡」之意",
             HOMOPHONE, "取自「朱古力新地/草莓新地」等真实在售品"),
        Wish("奶铁", "奶铁 → 「铁」谐音「铁定」，铁定脱单",
             HOMOPHONE, "网络通用谐音梗"),
        Wish("圆筒", "圆筒冰淇淋 → 「圆」谐音「缘」，团圆姻缘",
             HOMOPHONE, "「缘」为姻缘取意"),
        Wish("香芋", "香芋派 → 「芋」谐音「遇」，遇桃花",
             HOMOPHONE, "「遇」取相遇之意"),
        Wish("派", "派 → 派汽水，「派」有风风火火之意",
             LITERAL, "取「派」字吉祥义，字面取意不涉谐音"),
    ),
))

_reg(Theme(
    key="interview",
    name="offer在手",
    tagline="面试午餐，稳住别出错",
    voice="这是你未来三个月的第一顿团建。",
    kcal=640.0,
    tolerance=0.12,
    dessert_bias=0.35,
    blessing="HR 问你想吃什么，你说都行，然后加了个鸡腿。",
    provenance=(
        "热量 640 + 容差收到 12%（全局最严）：面试是高压场景，"
        "吃太撑会犯困、太乱会失态，因此容差比其余主题更紧。"
        "甜品关闭：正式场合不点甜品，这是品类规则而非口味偏好。"
    ),
    allow_dessert=False,
    wishes=(
        Wish("麦乐鸡", "麦乐鸡 → 「鸡」谐音「吉」，大吉大利拿 offer",
             HOMOPHONE, "取自真实在售品「麦乐鸡4块/麦乐鸡5块」；「鸡/吉」为常见谐音"),
        Wish("巨无霸", "巨无霸 → 气势压场，面试要有气场",
             HOMOPHONE, "取自真实在售品「巨无霸」"),
        Wish("吉士", "吉士 → 「吉」字开头，offer 也吉利",
             LITERAL, "「吉」为明确字面吉祥义"),
        Wish("玉米", "玉米杯 → 「玉」谐音「遇」，遇上面试官",
             HOMOPHONE, "「遇」为相遇取意"),
        Wish("双层深海鳕鱼", "鳕鱼 → 「学」谐音「学」，面试是学识考核",
             HOMOPHONE, "「鳕/学」为常见谐音"),
        Wish("奶铁", "奶铁 → 「铁」谐音「铁定拿 offer」",
             HOMOPHONE, "网络通用谐音梗"),
    ),
))

_reg(Theme(
    key="no-carb",
    name="轻装上阵",
    tagline="吃到撑，但热量不背锅",
    voice="想瘦又想吃满，这个诉求本身就很麦门。",
    kcal=520.0,
    tolerance=0.22,
    max_sodium=980.0,
    dessert_bias=0.0,
    allow_dessert=False,
    blessing="体重秤明天会感谢你，今天不会。",
    provenance=(
        "热量 520 + 甜品强制关闭 + 钠上限 980mg：这是唯一一个「清爽」型主题，"
        "因此约束最紧以支撑叙事。注意两个取值都是实测校准的结果而非拍脑袋——"
        "初版设 520±20%/钠 780mg 时，真实菜单上只能配出 420 kcal 的组合"
        "（命中数被迫下调且热量贴在带下沿），把容差放到 22%、钠放到 980mg 后"
        "才配出既清爽又贴预算的餐。注意：本主题不是减重方案，也不承诺减重效果"
        "——只承诺这顿更清爽。"
    ),
    wishes=(
        Wish("美式", "冰美式 → 「美式」谐音「美事」，好事将至",
             HOMOPHONE, "取自真实在售品「冰美式/热美式」系列"),
        Wish("玉米", "玉米杯 → 「玉」谐音「遇」，好运正在路上",
             HOMOPHONE, "「遇」为相遇取意"),
        Wish("蛋沙拉", "鲜蔬蛋沙拉 → 「蛋」谐音「单」，清爽单点",
             HOMOPHONE, "「单」取单点/单品之意"),
        Wish("茶", "柠檬红茶 → 「茶」谐音「查」，查无坏运",
             HOMOPHONE, "取自「阳光柠檬红茶」等真实在售品"),
        Wish("鳕鱼", "深海鳕鱼堡 → 「鳕」谐音「学」，学识与机会都深",
             HOMOPHONE, "「鳕/学」为常见谐音；取自真实在售品「双层深海鳕鱼堡」"),
    ),
))

_reg(Theme(
    key="heal",
    name="满血复活",
    tagline="昨天崩了，今天重开",
    voice="这顿是重启键，不是放纵键。",
    kcal=680.0,
    tolerance=0.15,
    dessert_bias=0.5,
    blessing="吃饱了。世界又可以了。",
    provenance=(
        "热量 680 中等、甜品中等：安慰性饮食需要「甜」但也需要「撑」，"
        "因此取中间位。主题不设钠加严——情绪场景下的克制是反直觉的，"
        "过度约束会让安慰失效，这一点写进 provenance 以备审阅。"
    ),
    wishes=(
        Wish("鸡腿", "板烧鸡腿堡 → 「鸡」谐音「吉」，大吉大利重新站起来",
             HOMOPHONE, "取自真实在售品「板烧鸡腿堡」；「鸡/吉」为常见谐音"),
        Wish("热朱古力", "热朱古力 → 「朱古力」谐音「主力」，补主力",
             HOMOPHONE, "取自真实在售品「热朱古力」"),
        Wish("麦旋酷", "麦旋风 → 「旋」谐音「全」，能量全开",
             HOMOPHONE, "取自真实在售品「麦旋酷阳光橙/奥利奥麦旋风」"),
        Wish("薯", "薯条 → 「薯」谐音「属」，属你回血",
             HOMOPHONE, "网络通用谐音梗"),
        Wish("双层", "双层 → 血量双层回满",
             HOMOPHONE, "与「复活」语义同向"),
        Wish("奶", "热牛奶 → 温热，字面意义上的暖胃",
             LITERAL, "字面取意"),
    ),
))

_reg(Theme(
    key="win-lottery",
    name="抽奖必中",
    tagline="不用抽奖，这份餐自己就是奖",
    voice="一等奖已经是你了，奖品先吃上。",
    kcal=640.0,
    tolerance=0.18,
    dessert_bias=0.55,
    blessing="开奖的时候记得回来告诉我。",
    provenance=(
        "热量 640、甜品中权：与「一夜暴富」同族但更低——"
        "抽奖是间歇性愉悦，一顿不必顶格。容差 18% 略宽，"
        "让「爆珠款」这类小份高趣味单品有机会入选。"
    ),
    wishes=(
        Wish("爆珠", "爆珠款 → 爆珠 = 爆中奖的珠子，字面即奖",
             LITERAL, "取自真实在售品「yeyeyeye爆珠款」"),
        Wish("yeyeyeye", "yeyeyeye → 「耶」是得手时的欢呼，中奖就该这么喊",
             LITERAL, "取自真实在售品「yeyeyeye奶冻款/爆珠款」的官方命名"),
        Wish("快乐", "蜜汁快乐 → 「快乐」字面即奖",
             LITERAL, "取自真实在售品「蜜汁快乐」"),
        Wish("果汁", "100%苹果汁 → 「果」谐音「过」，中奖过",
             HOMOPHONE, "「果/过」为常见谐音"),
        Wish("派", "香芋派/菠萝派 → 派奖的「派」",
             HOMOPHONE, "「派」取派奖之意"),
        Wish("双层", "双层 → 双重中奖",
             HOMOPHONE, "与「必中」语义同向"),
        Wish("绝代", "绝代双翅 → 「绝代」谐音「绝带」，中奖带，绝",
             HOMOPHONE, "取自真实在售品「绝代双翅」"),
    ),
))

_reg(Theme(
    key="travel",
    name="一路顺风",
    tagline="出发前吃好，路上别堵",
    voice="吃饱了才走得远，这顿是燃料不是享受。",
    kcal=720.0,
    tolerance=0.15,
    max_sodium=1490.0,
    dessert_bias=0.3,
    blessing="一路绿灯，别忘了把这份好运带上车。",
    provenance=(
        "热量 720 偏高且甜品低权：长途/行程场景需要的是扛饿的饱腹感，"
        "甜品在此只作收尾。钠上限 1490mg 是**实测校准**的结果——"
        "初版用通用线 1296mg 时，本主题 6 个锚点里只有「牛气」落在 612-828 kcal "
        "窗口内，严格档（3 梗）无解、只能放宽到 2 梗且只剩 1 个餐单；"
        "用 scripts/calibrate_travel.py 扫过后把钠放到 1.15 倍（1490mg），"
        "3 梗方案从 0 个增至 7 个。放宽钠而非放宽热量容差，是因为行程中缺水、"
        "钠高会更渴，这一取舍写进 provenance 备审。"
    ),
    wishes=(
        Wish("麦乐鸡", "麦乐鸡 → 「鸡」谐音「吉」，大吉大利一路顺风",
             HOMOPHONE, "取自真实在售品「麦乐鸡4块/麦乐鸡5块」；「鸡/吉」为常见谐音"),
        Wish("麦满分", "麦满分 → 出发前把「分」打满",
             BRAND, "品牌自带满分语义"),
        Wish("脆", "脆薯条/脆鸡 → 「脆」谐音「出」，一路出顺",
             HOMOPHONE, "「出」取出发行程顺利"),
        Wish("玉米", "玉米杯 → 「玉」谐音「遇」，遇路顺",
             HOMOPHONE, "「遇」为相遇取意"),
        Wish("麦香鱼", "麦香鱼 → 「鱼」谐音「余」，一路有余",
             HOMOPHONE, "取自真实在售品「麦香鱼」；anchor 收窄为「麦香鱼」而非「鱼」，"
                        "避免命中「专“薯鱼”你」这类营销梗名——梗要落在正经主食上"),
        Wish("牛气", "牛气满满 → 「牛气冲天」，气势上路一路顺",
             HOMOPHONE, "取自真实在售品「牛气满满」（官方命名自带「牛气」）；"
                        "「牛气冲天」为成语式取意。anchor 用「牛气」而非「牛堡」——"
                        "实测 6 款牛堡钠负荷 121-205mg/100kcal，与本主题 "
                        "钠上限结构性冲突，牛堡在本主题无解（scripts/calibrate_travel.py "
                        "可复现）。注意：牛气满满 495kcal 仍常被谐音更密集的组合压过，"
                        "故它多出现在第 2、3 号餐单而非首选——这是打分如实工作的结果，"
                        "不靠改预算迁就"),
    ),
))


THEME_ORDER: tuple[str, ...] = (
    "jackpot", "exam", "lovestruck", "interview",
    "no-carb", "heal", "win-lottery", "travel",
)


def all_wishes() -> tuple[Wish, ...]:
    """全部主题的谐音单元（去重前），供测试与审阅遍历。"""
    out: list[Wish] = []
    for k in THEME_ORDER:
        out.extend(THEMES[k].wishes)
    return tuple(out)


def anchors() -> tuple[str, ...]:
    """全部 anchor 去重集合，供批量核验。"""
    seen: dict[str, None] = {}
    for w in all_wishes():
        seen.setdefault(w.anchor, None)
    return tuple(seen)


def get(key_or_name: str) -> Theme:
    """按 key 或中文主题名取主题。"""
    k = key_or_name.strip()
    if k in THEMES:
        return THEMES[k]
    for t in THEMES.values():
        if t.name == k:
            return t
    lowered = k.lower()
    for t in THEMES.values():
        if t.name.lower() == lowered:
            return t
    raise KeyError(
        f"未知幸运主题：{key_or_name!r}。"
        f"可用 key：{', '.join(THEME_ORDER)}"
    )


def closest_key(key_or_name: str) -> str | None:
    """按子串猜主题 key（「暴富」→ jackpot）。猜不到返回 None。

    不做模糊匹配退化为无结果的假主题：宁可让上层追问用户。
    """
    k = key_or_name.strip().lower()
    if not k:
        return None
    for key in THEME_ORDER:
        if k in key or key in k:
            return key
    for t in THEMES.values():
        if k in t.name or t.name in k:
            return t.key
    for w in all_wishes():
        if k and k in w.gloss:
            return None
    return None