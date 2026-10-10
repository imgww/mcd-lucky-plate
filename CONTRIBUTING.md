# 贡献指南

感谢你愿意参与。先说三件最省时间的事。

## 一分钟了解

这是一个**只读** Skill：读麦当劳 MCP 的营养数据，在真实菜名上找谐音寓意，
解出一餐搭配。它**不产生订单**，不消耗券与积分，不改账户。

- 全部逻辑在 `src/`，零第三方依赖（仅 Python 标准库）
- 任何改动都必须**保持离线可复现**：不配 Token 也能跑通全部测试

## 环境

```bash
git clone https://github.com/imgww/mcd-lucky-plate.git
cd mcd-lucky-plate
python --version          # 需 3.10+

python scripts/check_environment.py    # 看环境是否就绪
python tests/test_lucky.py             # 2081 项断言，先跑一遍确认基线绿
```

`check_environment.py` 无 Token 时返回 `partial` 是**正常状态**——
离线模式完全可用，只影响实时取数。

## 你可以贡献什么

| 类型 | 适合谁 | 怎么做 |
|---|---|---|
| **加幸运主题** | 想要新梗 | 见下方「加一个主题」 |
| **补餐品寓意** | 发现漏项 | 改 `src/menu_luck.py` |
| **修锚点失效** | 菜单更新后 | 跑 `--anchors` 看未命中项 |
| **改进文档** | 觉得说明不够 | 改 `README.md` / `references/` |
| **提 Issue** | 发现 bug 或想要功能 | 直接开issue，模板见 `.github/` |

### 加一个主题

主题要作用在**约束**上，不能只换文案。否则 8 个主题会收敛成同一批餐品。

编辑 `src/lucky.py`，四件事都要做：

1. **选 anchor**：必须在真实菜单品名里出现的子串。先在
   [`docs/餐品幸运清单.md`](docs/餐品幸运清单.md) 里挑寓意，再据此定 anchor
2. **给独立约束**：`kcal` / `tolerance` / `max_sodium` / `allow_dessert`
3. **至少一个专属 anchor**：不能与已有主题共用全部 anchor，否则测试会失败
4. **写 `provenance`**：为什么是这个热量预算和钠上限

然后跑测试确认：

```bash
python tests/test_lucky.py            # 必须全绿
python src/lucky_plate.py --compare --offline samples/nutrition-foods.raw.json
```

看「不同首选方案数」是否 +1。如果你的主题和别的撞了，说明约束没拉开。

### 补餐品寓意

1. 跑 `python src/lucky_plate.py --anchors --offline samples/nutrition-foods.raw.json`
   看有没有未收录的品名
2. 在 `src/menu_luck.py` 对应位置加 `Luck(...)`
3. `score` 老实填：3 = 一听就成立，2 = 需解释一句，1 = 牵强
4. 跑 `python scripts/export_menu_luck.py` 重建清单文档
5. 跑测试确认覆盖率仍是 100%

**不要为了凑数硬编谐音。** 找不到合适的寓意就留空或标 `score=1`——
「诚实留空」比「编一个」有价值得多。

## 硬性规则

这些不是风格偏好，是本项目可复现性的基础：

1. **不许编造餐品**。所有 anchor 必须在 `list-nutrition-foods` 返回里真实命中。
   不确定就改窄，不要改宽。
2. **不许静默违背约束**。做不到就按 `RELAX_STEPS` 逐级放宽，并**打印放宽了什么**；
   全无解就如实报无解。
3. **不许承诺运势**。谐音是文案玩法，输出必须带「不构成运势或效果承诺」。
4. **零第三方依赖**。只用 Python 标准库，不引入包。
5. **不接入写操作工具**。`create-order` / `auto-bind-coupons` / `draw-lottery`
   一律不调用。
6. **凭据只走环境变量**，绝不写进任何文件。异常信息经 `mask_secret()` 脱敏。
7. **样本入库前必须脱敏**——跑 `python docs/sanitize_sample.py`。

## 提交前自查

```bash
python tests/test_lucky.py                    # 2081 项断言
python scripts/check_environment.py           # 环境状态
python src/lucky_plate.py --compare --offline samples/nutrition-foods.raw.json
```

如果改了 `menu_luck.py`，还要：

```bash
python scripts/export_menu_luck.py
python docs/make_figs.py
```

## 代码风格

跟着现有代码走，不引入新范式：

- 类型注解齐全，`from __future__ import annotations`
- 中文注释解释**为什么**，不复述代码在做什么
- 每个约束取值都要能说出依据（实测？通用线？叙事需要？）
- 测试断言里写清失败原因，别只写 `assert x == y`

## 报告问题

开issue 时带上：

- 你执行的确切命令
- 实际输出（完整贴，别只贴最后一行）
- 你期望的结果
- 环境信息（`python --version`、是否配了 Token）

如果涉及菜单数据，请附上 `--anchors` 的输出——能直接看出是不是数据变了。

## 不做的事

- 不接入任何下单/领券/抽奖工具
- 不做减重承诺、节食方案、临床营养建议
- 不做与其他品牌的横向对比
- 不把谐音包装成运势预测

## 许可

代码以 MIT 许可开放。提交即表示同意。
赛事声明与商标归属见 [`CONTEST_DECLARATION.md`](CONTEST_DECLARATION.md)。