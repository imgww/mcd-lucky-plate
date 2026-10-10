# 环境配置指引 · setup-guide

本 Skill **零第三方依赖**，只需 Python 3.10+。MCP Token 只有联网模式才需要。

依赖清单见 `skill-dependencies.md`；本文按其中的依赖 id 分节，
每节对应清单里的一条依赖，缺哪节就补哪节。

---

## 依赖 `python-runtime`（必需）

### 检查

```bash
python --version
```

需 3.10 及以上（源码用了 `X | None` 联合类型注解）。

若低于 3.10：升级，或手工把 `src/` 下的 `X | None` 改成 `Optional[X]`
并同步修改 import。**不建议手工改**——改完必须重跑 `python tests/test_lucky.py` 确认无回归。

### 安装

- 官方主页：<https://www.python.org/downloads/>
- 官方文档：<https://docs.python.org/3/>

从官网下载安装，无需 `pip install` 任何包。

### 低于最低版本时

所有功能（主题投影、谐音锚点检索、约束求解、组合配餐、差异化报告）
都会受影响。升级 Python 是唯一可靠路径；手工改写注解后必须复跑全部测试。
无法升级且不手工改写时停止，不使用行为未知的解释器继续。

---

## 依赖 `nutrition-sample`（必需）

`samples/nutrition-foods.raw.json` 是麦当劳 MCP `list-nutrition-foods` 的真实响应快照，
已脱敏入库，是离线模式与全部测试的数据来源。

### 检查是否就绪

```bash
python scripts/check_environment.py
```

状态行应显示「样本已就绪」。

### 缺失时怎么办

1. 配置 `MCD_MCP_TOKEN`（见下一节）
2. 拉取实时数据并落盘：
   ```bash
   python src/lucky_plate.py --theme exam --probe-dump samples/nutrition-foods.raw.json
   ```
3. 脱敏后入库：确认不含 Token 与任何个人标识
4. 重建餐品幸运清单：`python scripts/export_menu_luck.py`

样本缺失时，测试会自动改用 `tests/fixtures/` 合成夹具运行核心断言，
并把依赖真实菜单的断言显式标记为**跳过**，不伪装成通过。

---

## 依赖 `mcd-mcp`（可选，仅联网模式需要）

### 官方入口

| 项 | 值 |
|---|---|
| 控制台 | <https://open.mcd.cn/mcp> |
| 服务端仓库 | <https://github.com/M-China/mcd-mcp-server> |

### 获取 Token

1. 打开 <https://open.mcd.cn/mcp>
2. 右上角点「登录」，用手机号验证
3. 登录成功后右上角变为「控制台」，点击打开
4. 点「激活」申请 MCP Token，阅读并同意服务协议
5. 复制 Token

### 配置为环境变量

**只走环境变量，不要写进任何文件。**

```bash
# macOS / Linux / Git Bash
export MCD_MCP_TOKEN="你的Token"

# Windows PowerShell
$env:MCD_MCP_TOKEN = "你的Token"
```

可选环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `MCD_MCP_TOKEN` | 无 | **必填**，MCP Token |
| `MCD_MCP_URL` | `https://mcp.mcd.cn` | 服务地址 |
| `MCD_MCP_TIMEOUT` | `60` | 单次请求超时秒数 |

### 权限范围

本 Skill 只调用 `list-nutrition-foods`（只读、零必填参数、不依赖门店与登录态）。
**不接入** `create-order`、`auto-bind-coupons`、`draw-lottery` 等写操作工具，
也不接入 `query-my-*` 个人资产查询。不需要门店信息、配送地址或会员资产。

### 验证

```bash
python src/lucky_plate.py --list-tools
```

应输出 `MCP 连通正常，共 35 个工具。`

### 轮换与撤销

重新到控制台激活即可获得新 Token，旧 Token 立即失效；
本地删除环境变量即可停止使用。Token 泄露时立刻执行这两步。

### 配置失败时的降级

Token 未设置、认证失效或服务不可达时，自动改用离线样本求解，
算法与约束完全一致，输出中会标注当前为离线数据。
只有实时在售状态与价格无法校验。

---

## 离线模式（无需 Token，推荐先跑通）

仓库自带已脱敏的真实响应快照，直接可用：

```bash
python src/lucky_plate.py --theme 一夜暴富 --offline samples/nutrition-foods.raw.json
python src/lucky_plate.py --compare --offline samples/nutrition-foods.raw.json
python src/lucky_plate.py --anchors --offline samples/nutrition-foods.raw.json
python tests/test_lucky.py
```


## 在 MCP 客户端里配置（可选）

把 `mcp-config.example.json` 里的 `mcpServers` 段粘贴进客户端的自定义连接器配置，
替换 `${MCD_MCP_TOKEN}` 后即可在对话中调用。

**注意**：新 MCP 不会自动激活，需在连接器管理页右上角的自定义连接器入口
点击「信任」后启用。

---

## 安全须知

- Token **只**存于环境变量，绝不写入源码、日志、异常信息或任何提交文件
- `.gitignore` 已拦截 `.env` / `*token*` / `*secret*` / `mcp-config.json`
- 异常信息经 `mask_secret()` 兜底脱敏，Token 不会出现在报错里
- 样本文件入库前已脱敏，不含凭证与个人信息

若 Token 泄露：到 <https://open.mcd.cn/mcp> 重新激活，旧 Token 即失效；
本地删除环境变量即可停止使用。