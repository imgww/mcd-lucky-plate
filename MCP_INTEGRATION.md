# MCP_INTEGRATION.md · 麦当劳 MCP 集成与下单链路契约

本文件描述本 Skill **真实发生**的调用，以及它刻意**不调用**的部分。
不含设想中未接入的能力。

---

## 一、使用的 MCP Server

| 项 | 值 |
|---|---|
| Server 名称 | `mcd-mcp` |
| Server 版本 | `1.0.0` |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输方式 | streamable HTTP（JSON-RPC 2.0 over HTTP POST） |
| 协议版本 | `2025-06-18` |
| 鉴权 | HTTP 请求头 `Authorization: Bearer <MCP Token>` |
| 会话特性 | 服务端为**无状态**：`initialize` 响应头不下发 `mcp-session-id`。客户端仍透传该头，以便将来有状态时无需改动 |
| 声明的能力 | `tools`（无 `resources` 与 `prompts`） |
| 服务端工具总数 | 35（经 `tools/list` 实测，单页返回、无分页游标） |
| 客户端实现 | `src/mcp_client.py`，纯标准库自研，不依赖 MCP SDK |
| 服务规则 | 遵守麦当劳 MCP 服务规则 <https://cdn.mcd.cn/cms/pages/MCPServerRules.html> |

---

## 二、实际调用的 Tool

### 2.1 业务数据工具（1 个）

#### `list-nutrition-foods`

| 项 | 说明 |
|---|---|
| 作用 | 获取麦当劳常见餐品的营养成分：能量、蛋白质、脂肪、碳水化合物、钠、钙 |
| 入参 | **无必填参数**，本 Skill 以 `{}` 调用 |
| 调用点 | `src/nutrition.py` → `fetch_foods()` |
| 调用时机 | 每次 CLI 运行开始时调用 1 次；`--offline` 模式下不调用 |
| 副作用 | 无（只读查询） |
| 是否依赖登录会员态 | 否 |
| 是否依赖门店/地理位置 | 否 |

**为什么选它作为唯一数据源**：在 35 个工具里，`list-nutrition-foods` 与
`now-time-info` 是仅有的两个「零必填参数 + 纯只读 + 不依赖门店与登录态」的工具。
任何评审者拿到仓库、配上自己的 Token 就能完整复现。可复现性是设计底线。

**关键坑**：`data` 不是数组也不是对象，而是一段带表头的字符串表格：

```
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,
      carbohydrate,sodium,calcium}:
  猪柳麦满分,null,1288,308,16,16,24,781,213
```

按常规 JSON 思路去 `payload["data"]` 取字典列表会拿到 0 条记录。
首行 `[N]{列名…}:` 声明行数与列名，其后每行一条记录、两空格缩进、逗号分隔、
缺失值为字面量 `null`。解析器按表头列数严格校验，列数不符的行**跳过而非猜测**。

**数据规模**：原始 160 行 → 去重后 158 个唯一名 → 丢弃 4 条能量为 0 的记录
→ **154 条可用**。

**本 Skill 依赖的另一件事**：响应**不含品类字段**，`category` 由 `nutrition.py`
按商品名关键词推断（`category_derived=True` 标记来源）。谐音词库里的
`anchor` 检索**不使用**品类字段，只对品名做子串匹配，因此不受该派生字段影响。

### 2.2 协议与自检工具（不承载业务）

| Tool | 用途 |
|---|---|
| `tools/list` | `--list-tools` 自检，确认 Token 有效、连通正常、可查工具总数 |

---

## 三、下单链路契约（本 Skill 只指引，不执行）

这一节是本 Skill 区别于纯只读工具的地方：**它关心怎么把餐单变成订单**，
但**不代用户下单**。以下参数规则于 2026-10-09 从 MCP 工具 schema 实测校准。

### 3.1 为什么停在品名级

| 事实 | 后果 |
|---|---|
| `list-nutrition-foods` 返回营养成分，**不含 `productCode`** | 餐单只能到品名级 |
| `productCode` 只能由 `query-meals` 取得，且**需先有 `storeCode`** | 拿编码必然引入门店/地理位置依赖 |

若为拿编码而接入门店链路，餐单就无法离线复现——任何人 clone 后配自己的 Token
都跑不通。因此本 Skill 产出**品名级**方案，并在每个方案上标注
`needs_code_lookup: true`，提醒下单前需现查编码。

### 3.2 四步链路

```
① query-nearby-stores   选门店 → storeCode（beType=5 时还得 beCode）
② query-meals           按 storeCode 拉该店在售餐品 → productCode + 价格
③ calculate-price       用 productCode 试算 → 确认金额 + takeWayCode
④ create-order          用户明确确认后下单
```

### 3.3 参数规则（实测）

| 场景 | `orderType` | `beType` | `beCode` | 其他必传 |
|---|---|---|---|---|
| 到店自取 | 1 | 1 | **不传** | `takeWayCode` |
| 得来速（车道取餐） | 1 | 5 | **必传**（来自 `query-nearby-stores`） | `takeWayCode` |
| 麦乐送到家 | 2 | 2 | **必传**（来自 `delivery-query-stores`） | `addressId` |
| 企业团餐 | 2 | 6 | **必传** | `gmServiceCode` |

**三个字段任何场景都必填**：`storeCode`、`orderType`、`beType`。

### 3.4 六个易踩的坑

1. **价格单位是分**，展示需 ÷100 转元。
2. **`takeWayCode` 只在 `orderType=1` 时必传**，且值来自 `calculate-price` 返回的
   `data.takeWayList[].code`——不是自己编的。
3. **套餐子项走 `items[].roundList`**，与单点商品的 `items[].productCode` 结构不同。
4. **特制项 `key` 有传参规则**：选中的用 `selectedKey`，未选中的若 `unselectedKey`
   非空**也必须传**。漏传会导致下单参数不完整。
5. **`reservationDate` 仅预约场景传**，格式 `yyyy-MM-dd HH:mm`；非预约场景不传。
6. **`beCode` 与 `beType` 强绑定**：`beType=5/2/6` 必传，`beType=1` 传了反而可能出错。

### 3.5 为什么不代下单

`create-order` 会产生**真实订单与支付链路**。本 Skill 的价值主张是
「算清楚 + 说清楚怎么点」，不是替用户花钱。任何一步都应停在用户确认前。

---

## 四、明确**不使用**的工具及理由

35 个工具中其余 33 个本 Skill 刻意不接入：

| 类别 | 代表工具 | 不接入的理由 |
|---|---|---|
| 下单与取消 | `create-order`、`cancel-order`、`calculate-price` | 产生真实订单与支付链路，有资损风险。本 Skill 只输出链路指引，不调用 |
| 券与积分写操作 | `auto-bind-coupons`、`draw-lottery`、`mall-create-order` | 改变用户券资产、原子扣减积分 |
| 个人资产查询 | `query-my-account`、`query-my-coupons`、`order-list`、`query-my-prizes` | 依赖登录会员态，评审无法复现，且涉及个人信息 |
| 门店/地址上下文 | `query-nearby-stores`、`query-meals`、`query-store-coupons`、`delivery-*` | 需要 `storeCode`/`addressId`，把结果绑死在特定地理位置上——这正是停在品名级的原因 |
| 派对预约链路 | `query-party-*`、`party-order-create` | 多级下钻依赖 `spuId`，与「配一餐」无关 |
| 活动日历 | `campaign-calendar` | 输出随时间漂移，与谐音配餐无因果关系 |

**这条边界是有意为之的设计声明**：本 Skill 的价值主张是
「真实数据 + 可核验的谐音 + 清楚的下一步」，不代用户做任何有资产后果的动作。

---

## 五、调用流程

```
用户 CLI 命令
    │
    ├─(A) --offline 分支 ─────────────────────────┐
    │                                             │
    └─(B) 在线分支                                 │
         │                                        │
         1. POST initialize                       │
         2. POST notifications/initialized  → 202 │
         3. POST tools/call                       │
              {name:"list-nutrition-foods",        │
               arguments:{}}                      │
            ← result.content[].text               │
                                                    ▼
         4. 解析 data 字符串表格 + 字段归一化（154 项）
         5. 谐音锚点检索：anchor in food.name（lucky_engine.resolve_anchors）
         6. 主题感知配平：硬约束 + 谐音加权打分（compose_lucky）
         7. 输出餐单 + 谐音明细 + 下单链路指引
```

**调用强度**：单次运行 3 个 HTTP 请求（2 次握手 + 1 次工具调用），
一次调用即返回全部 160 行营养表并在本地清洗。无轮询、无并发、无写操作。
`--offline` 模式 0 请求。

---

## 六、业务价值

### 6.1 它替代了什么人工动作

「给一顿饭讨个吉利」这件事，人是怎么做的：翻菜单 → 看到「板烧鸡腿堡」→
想到「鸡」谐音「吉」→ 觉得吉利 → 但**不确定这个梗是不是只有自己懂**，
也不知道这一顿加起来多少热量。

本 Skill 把「翻菜单找梗」变成「给一个主题，出带谐音溯源的一餐」：
**娱乐化表达 → 可核验的决策辅助**。

### 6.2 价值落点

| 对象 | 价值 |
|---|---|
| 用户 | 一份谐音逐条对应真实菜名的餐单 + 完整营养拆解 + 怎么下单的参数清单 |
| 麦当劳 | 谐音玩法让菜单命名本身成为可分享的内容资产——「麦满分」这类命名天然适配 |
| MCP 生态 | 示范**主观内容**（谐音词库）如何与**硬约束**（营养）合成可复现求解，而不是只做文案 |
| 后续开发者 | `lucky.py` 的词条结构（anchor/gloss/kind/note）是可审计的主观知识表示范式 |

### 6.3 可验证性

- **561 项离线回归断言**，`python tests/test_lucky.py`，不依赖网络与 Token：
  - 谐音锚点在真实菜单中逐条命中（50 条）
  - 8 个主题产出 8 种不同首选（`compare_themes`）
  - 逐主题逐方案校验热量容差、钠上限、甜品开关
  - `luck_score` 与实数谐音命中数一致
  - 确定性：同输入两次运行 md5 一致；打乱菜单顺序输出不变
  - 显式设定的谐音下限不可达时**必须**返回无解（有断言，防静默降级）
- 合成夹具与真实数据物理隔离：夹具在 `tests/fixtures/`，真实响应在 `samples/`
- 样本缺失时测试自动跳过依赖真实菜单的断言，**不伪装成通过**

---

## 七、合规对照

| 规则要求 | 本项目落实 |
|---|---|
| 真实使用麦当劳 MCP 能力 | 主链路 `list-nutrition-foods` 实时取数，无内置兜底营养表；离线模式仅用于测试且明确标注数据来源 |
| 配置仅用环境变量占位符 | `mcp-config.example.json` 全占位符；`.gitignore` 拦截 `.env` / `*token*` / `*secret*` |
| 不含真实 Token / 个人信息 | 代码与文档零凭证；不接入任何返回个人资产的 `query-my-*` 工具 |
| 不宣扬不健康饮食方式 | 定位为「均衡搭配 + 谐音玩法」，不含减重承诺与节食方案；「轻装上阵」主题明确声明不承诺减重效果 |
| 不与其他品牌产品对比 | 数据源仅麦当劳自有营养库，输出仅在麦当劳餐品之间做组合 |
| 不构成医疗/营养专业建议 | CLI 每次输出打印该声明 |
| 不做不实承诺 | 谐音与吉祥话仅为文案玩法，**不构成任何运势或效果承诺**，该声明固定打印 |