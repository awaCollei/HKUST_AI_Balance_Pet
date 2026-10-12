# 余额桌面宠物

以项目根目录的 `pet.png` 为形象，通过 HKUST GenAI 余额接口显示余额的透明桌面宠物。

## 功能

- 左键拖动；宠物位于当前屏幕左半边时自动水平翻折。
- 左键单击播放 Q 弹拉伸动画，并异步查询余额。
- 气泡会出现在宠物朝向屏幕内部的一侧，由两个小圆和一个带边框的大椭圆组成。
- 余额固定显示三位小数；请求有 5 秒冷却，网络请求不会阻塞界面。
- 右键菜单可调整为 75% / 100% / 125% / 150%、收到托盘或退出。
- 单击或双击托盘图标可恢复宠物；位置和大小会自动保存。

## 环境要求

- Python 3.11+
- Windows / Linux 桌面环境（托盘功能需要系统托盘支持）

## 安装与运行

推荐使用 `uv`：

```bash
uv sync
copy .env.example .env
```

Linux/macOS 下复制配置文件：

```bash
cp .env.example .env
```

编辑 `.env`，只填写 Bearer 密钥本身：

```dotenv
HKUST_BEARER_TOKEN=你的密钥
```

启动：

```bash
uv run balance-pet
```

没有 `uv` 时也可使用：

```bash
python -m venv .venv
# Windows
.venv\Scripts\pip install -e .
.venv\Scripts\balance-pet.exe
# Linux
# .venv/bin/pip install -e . && .venv/bin/balance-pet
```

> `.env` 已被 `.gitignore` 排除，不要提交真实密钥。未配置密钥时，单击宠物会显示“未配置密钥”。

## 操作

| 操作 | 效果 |
| --- | --- |
| 左键拖动 | 移动宠物，跨过屏幕中线时自动翻折 |
| 左键单击 | Q 弹动画并查询/显示余额 |
| 右键 | 打开大小、托盘和退出菜单 |
| 托盘图标单击/双击 | 恢复宠物 |

## 开发检查

```bash
uv run pytest
uv run ruff check .
```

接口固定为 `https://hkust.azure-api.net/hkust-genai-auth/v1/balance`，请求头为 `Authorization: Bearer <HKUST_BEARER_TOKEN>`。响应体按纯文本裸数字解析，例如 `12.3456`。
