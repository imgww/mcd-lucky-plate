# workbuddy.md · 开发对话上下文

> 面向后续接手者（人或 AI）的交接说明。记录**为什么这样设计**，
> 而不是重复 README 已经写过的内容。

## 一、这个 Skill 在项目里的位置

M-CODE 参赛项目 `plan-and-design/` 下有三个同源 Skill：

| 项目 | 决策单位 | 核心主张 |
|---|---|---|
| `mcd-weekly-plate` | 一周 | 带硬约束的跨天束搜索 |
| `mcd-soul-plate` | 一餐 | 人格 → 约束的翻译 |
| **`mcd-lucky-plate`（本项目）** | 一餐 | **主观内容（谐音）+ 硬约束**的合成 |

前两者共享 `nutrition.py` / `composer.py` / `mcp_client.py` 三个基础模块，
本项目同样复用——**这不是重复，是刻意保持同一套数值口径**（蛋白 3.2g/100kcal、
钠满意线 260mg/100kcal），使三个 Skill 的输出可横向比较。

## 二、复用与新增的边界

**直接复用**（未改动）：`nutrition.py`、`composer.py`、`mcp_client.py`、`textfmt.py`

**新增**：
- `lucky.py` — 8 主题 + 50 条谐音词库。唯一主观内容源
- `lucky_engine.py` — 锚点检索 / 主题感知配平 / 差异化验证
- `lucky_plate.py` — CLI

**关键设计**：主题差异必须作用在**约束**上而不只是文案上。
若只换文案，8 个主题会收敛到同一批万金油餐品——这是实测发现的，
不是理论担忧。因此每个 `Theme` 自带 `kcal`/`tolerance`/`max_sodium`/
`allow_dessert`/`dessert_bias`，打分里谐音权重 0.46 为最高。

## 三、开发过程中真实踩到的坑

### 1. 谐音锚点写了三个不存在的品名

初版词库有 `鲈`（来自营养说明字段）、`扭蛋`、`开心`（凭印象写的）——
菜单里根本没有。**这是"编造餐品"的真实风险**。

修法：把「锚点必须在真实菜单命中」做成硬门禁——
`--anchors` 命令 + 测试断言 + 环境检查脚本三重覆盖。
修正后 50/50 全部命中。

**教训**：谐音玩法的可信度完全取决于锚点是否真实。
任何"看起来很顺"但没在菜单里核对过的词，都是负资产。

### 2. 「一夜暴富」在严格钠线下数学上无解

初版按通用线给钠上限 1404mg，结果 8 个主题里 7 个可解、jackpot 无解。

写了 `scripts/calibrate_jackpot.py` 扫 600–780 kcal 共 10 档预算，
结论是**无一能在严格钠线下解出**。根因：jackpot 的锚点
（巨无霸/双层/牛气/鸡腿/麦满分）全部指向高蛋白主食，实测单品钠 728–1373mg，
两件主食必然超钠。

**处理**：把钠上限**显式**放宽到 2106mg 写进 `provenance`，而不是让引擎悄悄放宽。
诚实代价：jackpot 成为钠最高的主题，并在 README「诚实边界」里点名。

### 3. 「轻装上阵」配出 420 kcal（预算 520）

初版 520±20% / 钠 780mg 太紧，真实菜单上只能凑出 420 kcal 的组合。
放宽到 ±22% / 980mg 后配出 537 kcal，既清爽又贴预算。

**两个主题的约束都是实测校准出来的，不是拍脑袋。** 这个事实写在
`lucky.py` 的 `provenance` 里，可审计。

### 4. 测试抓到一个真 bug：显式下限被静默推翻

`--min-hits 99` 时，回退逻辑一路把下限降到 1 个，等于**悄悄推翻用户要求**
还给出个"看起来满足"的方案。这违反诚实底线。

修法：`min_hits` 由用户显式指定时视为**硬约束**，不参与自动放宽；
超过可得锚点数时直接返回无解并说明。并补了回归断言锁死。

**教训**：自动放宽是好的贴心，但必须区分「我替你放宽」和「你要求的」。

### 5. 一条不能靠双引号 bash 的教训

写校准脚本时用 `bash -c "python -c '...'"` 嵌套传参，脚本里对空集合调 `max()`
直接抛 `ValueError`。改成 `Write` 落成 `scripts/calibrate_jackpot.py`
再执行，问题定位清晰且可复跑。

## 四、为什么停在品名级（最重要的设计决策）

用户需求里明确说了「引导用户链接 MCP 完成在线点餐」。这里有个真实的张力：

- 要下单就必须有 `productCode`
- `productCode` **只能**由 `query-meals` 取得，且需先有 `storeCode`
- 一旦接入门店链路，餐单就无法离线复现

兄弟项目 `mcd-weekly-plate` 与 `mcd-soul-plate` 都选了纯只读。
本项目在「引导下单」上的处理是**第三条路**：

1. 餐单停在品名级，显式标注 `needs_code_lookup: true`
2. `--order-help` 输出完整四步链路与参数陷阱（schema 实测校准）
3. **不调用任何写操作工具**——下单由用户确认后自己执行

这样既回应了「引导点餐」的需求，又不引入资损风险与不可复现性。

## 五、待办与建议

- [ ] **出图文报告**。可摘 `mcd-weekly-plate` 的 `render.py`（零依赖单文件 HTML），
      做成 8 主题 × 谐音标注的可视化，是最省力且效果最好的下一步
- [ ] **词库扩充**。当前 50 条锚点，可按主题补更多（每个主题保底 6–8 条）
- [ ] **口味偏好建模**。当前无忌口/辣度维度
- [ ] **若要真下单**，需先决策是否接受门店依赖——建议做成独立可选模块，
      而非改主链路
- [ ] `no-carb` 主题名可能被误解为"低碳"，实际只是"清爽低热量"，
      可考虑改名为 `light-load`

## 六、复现全部结论

```bash
# 环境自检（含谐音锚点核验）
python scripts/check_environment.py

# 8 主题 8 种答案
python src/lucky_plate.py --compare --offline samples/nutrition-foods.raw.json

# 50 条锚点逐条核验
python src/lucky_plate.py --anchors --offline samples/nutrition-foods.raw.json

# 561 项回归断言
python tests/test_lucky.py

# jackpot 约束校准（复现「严格钠线无解」的结论）
python scripts/calibrate_jackpot.py
```

无需 Token、无需网络。