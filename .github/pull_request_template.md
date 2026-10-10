# 这个 Skill 做什么

用户说「今天想讨个吉利」，它给出一顿**谐音真的落在菜单上**的麦当劳搭配，
再告诉用户怎么把它变成真实订单。

技术主张只有一条：**谐音不是文案层的事，必须落在约束层。**

## 硬性规则

这些不是风格偏好，是本项目可复现性的基础：

1. **不许编造餐品**。所有 anchor 必须在 `list-nutrition-foods` 返回里真实命中。
   不确定就改窄，不要改宽。
2. **不许静默违背约束**。做不到就按 `RELAX_STEPS` 逐级放宽，并**打印放宽了什么**；
   全无解就如实报无解。
3. **不许承诺运势**。谐音是文案玩法，输出必须带「不构成运势或效果承诺」。
4. **零第三方依赖**。只用 Python 标准库。
5. **不接入写操作工具**。`create-order` / `auto-bind-coupons` / `draw-lottery`
   一律不调用。
6. **凭据只走环境变量**，绝不写进任何文件。异常信息经 `mask_secret()` 脱敏。
7. **样本入库前必须脱敏**，跑 `python docs/sanitize_sample.py`。

## 提交前必须通过

```bash
python tests/test_lucky.py      # 2081 项断言，须全绿
python scripts/check_environment.py
```

若改了 `src/menu_luck.py`，还需：

```bash
python scripts/export_menu_luck.py   # 重建清单文档
python docs/make_figs.py             # 重建配图
```

## 改动要点

<!-- 说明你改了什么、为什么 -->

## 自查

- [ ] `python tests/test_lucky.py` 全绿
- [ ] `python src/lucky_plate.py --compare --offline samples/nutrition-foods.raw.json` 的「不同首选方案数」没有下降
- [ ] 若改菜单或词库：`--anchors` 无新增未命中项
- [ ] 输出里没有新增任何"保证运势"类表述
- [ ] 没有引入第三方依赖
- [ ] 没有调用任何写操作工具
- [ ] 离线模式（不带 Token）仍可完整复现

## 关联

<!-- Closes #123 -->