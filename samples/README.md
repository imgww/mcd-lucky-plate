# samples/

本目录存放**从麦当劳 MCP 实时拉取的原始响应样本**，用途是让评审在不配置 Token 的情况下离线复现配平结果。

## 生成方式

```bash
export MCD_MCP_TOKEN=你的Token
python src/weekly_plate.py --probe-dump samples/nutrition-foods.raw.json
```

该命令只做一次 `tools/call` 调用 `list-nutrition-foods`，把服务端返回的 JSON 原样落盘，不做任何加工。

## 为什么默认是空的

`.gitignore` 已忽略 `samples/*.raw.json`。原因有两条：

1. 拉取动作依赖你个人的 MCP Token 与会员身份，产物可能夹带与账户相关的上下文字段；入库前必须**人工逐字段检查**，确认无个人信息、无凭证后才手动 `git add -f`。
2. 营养数据以官方实时结果为准，仓库里固化一份快照容易过期误导。

## 数据真实性约定

本目录只接受 MCP 真实响应。算法逻辑的测试夹具在 `tests/fixtures/`（单日用 `synthetic_nutrition.json`、周模式用 `synthetic_nutrition_week.json`），那些是**人为构造的合成数据，不是麦当劳餐品数据**，两者不得混用。
