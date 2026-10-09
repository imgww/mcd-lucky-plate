# 下单链路速查 · ordering-playbook

> 从「麦门幸运餐盘」的餐单，到麦当劳 MCP 里的真实订单。
> 参数规则于 2026-10-09 从 MCP 工具 schema 实测校准。

## 为什么本 Skill 停在品名级

`list-nutrition-foods` 只给营养成分，**没有 `productCode`**。
编码只能由 `query-meals` 在**确定门店之后**取得，因此天然依赖 `storeCode`。

若为拿编码而接入门店链路，餐单就无法离线复现。所以本 Skill 产出品名级方案，
并标注 `needs_code_lookup: true`。

## 四步链路

| 步骤 | 工具 | 产出 | 必传参数 |
|---|---|---|---|
| ① 选门店 | `query-nearby-stores` | `storeCode`（beType=5 时另有 `beCode`） | `beType`、`searchType`；searchType=2 时另需 `city`+`keyword` |
| ② 看菜单 | `query-meals` | `productCode`、价格、套餐结构 | `storeCode`、`orderType`、`beType` |
| ③ 试算 | `calculate-price` | 总价、`takeWayList[].code` | 同上 + `items[]` |
| ④ 下单 | `create-order` | 订单、支付链接 | 同上 + `takeWayCode`（orderType=1） |

## 场景 × 参数对照

| 场景 | `orderType` | `beType` | `beCode` | 其他必传 |
|---|---|---|---|---|
| 到店自取 | 1 | 1 | **不传** | `takeWayCode` |
| 得来速（车道取餐） | 1 | 5 | **必传** | `takeWayCode` |
| 麦乐送到家 | 2 | 2 | **必传** | `addressId` |
| 企业团餐 | 2 | 6 | **必传** | `gmServiceCode` |

**`storeCode`、`orderType`、`beType` 三者任何场景都必填。**

## 六个坑

1. **价格单位是分**，展示 ÷100。
2. **`takeWayCode` 只在 `orderType=1` 传**，值来自 `calculate-price` 的
   `data.takeWayList[].code`，不是自己编。
3. **套餐走 `items[].roundList`**，与单点的 `items[].productCode` 结构不同。
4. **特制项 `key` 规则**：选中用 `selectedKey`；未选中若 `unselectedKey` 非空
   **也必须传**，漏传会导致参数不完整。
5. **`reservationDate` 仅预约场景传**（`yyyy-MM-dd HH:mm`），非预约不传。
6. **`beCode` 与 `beType` 强绑定**：`beType=1` 传了反而可能出错。

## 团餐价位带搭配规则

`query-meals` 在企业团餐场景下给出的搭配建议：

| 价位 | 建议搭配 |
|---|---|
| 20 元以下 | 小食 |
| 20–30 元 | 汉堡 + 小食，或 汉堡 + 饮料 |
| 30–40 元 | 汉堡 + 薯条/小食 + 饮料 |
| 40–50 元 | 汉堡 + 薯条 + 小食 + 饮料 |
| 50 元以上 | 丰富组合，优先不重复小食 |

## 本 Skill 不做什么

- **不调用上述任何一步。** 下单是有资损的动作，须由用户本人确认后执行。
- **不产生真实订单**，不占用券与积分资产。
- **不猜编码**：没有 `productCode` 就如实说需要现查，不用假编码顶替。

餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准。