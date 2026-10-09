# 环境配置指引 · setup-guide

本 Skill **零第三方依赖**，只需 Python 3.10+。MCP Token 只有联网模式才需要。

---

## 一、Python（必需）

### 检查

```bash
python --version
```

需 3.10 及以上（源码用了 `X | None` 联合类型注解）。

若低于 3.10：升级，或手工把 `src/` 下的 `X | None` 改成 `Optional[X]`
并同步修改 import。**不建议手工改**——改完必须重跑 `python tests/test_lucky.py` 确认无回归。

### 安装

从 <https://www.python.org/downloads/> 下载安装，无需 `pip install` 任何包。

---

## 二、离线模式（无需 Token，推荐先跑通）

仓库自带已脱敏的真实响应快照，直接可用：

```bash
python src/lucky_plate.py --theme 一夜暴富 --offline samples/nutrition-foods.raw.json
python src/lucky_plate.py --compare --offline samples/nutrition-foods.raw.json
python src/lucky_plate.py --anchors --offline samples/nutrition-foods.raw.json
python tests/test_lucky.py
```

---

## 三、联网模式（需 Token）

### 1. 获取 Token

1. 打开 <https://open.mcd.cn/mcp>
2. 右上角点「登录」，用手机号验证
3. 登录成功后右上角变为「控制台」，点击打开
4. 点「激活」申请 MCP Token，阅读并同意服务协议
5. 复制 Token

### 2. 配置为环境变量

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

### 3. 自检

```bash
python src/lucky_plate.py --list-tools
```

应输出 `MCP 连通正常，共 35 个工具。`

### 4. 运行

```bash
python src/lucky_plate.py --theme exam
```

---

## 四、在 MCP 客户端里配置（可选）

把 `mcp-config.example.json` 里的 `mcpServers` 段粘贴进客户端的自定义连接器配置，
替换 `${MCD_MCP_TOKEN}` 后即可在对话中调用。

**注意**：新 MCP 不会自动激活，需在连接器管理页右上角的自定义连接器入口
点击「信任」后启用。

---

## 五、安全须知

- Token **只**存于环境变量，绝不写入源码、日志、异常信息或任何提交文件
- `.gitignore` 已拦截 `.env` / `*token*` / `*secret*` / `mcp-config.json`
- 异常信息经 `mask_secret()` 兜底脱敏，Token 不会出现在报错里
- 样本文件入库前已脱敏，不含凭证与个人信息

若 Token 泄露：到 <https://open.mcd.cn/mcp> 重新激活，旧 Token 即失效；
本地删除环境变量即可停止使用。