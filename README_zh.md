# pystores

**面向服务端 Python UI 的框架无关状态管理库。**

为 NiceGUI 及其他服务端 UI 框架提供声明式、多用户隔离的状态管理。

[English](https://github.com/SparkBayes/pystores/blob/main/README.md) | **简体中文**

[![CI](https://img.shields.io/github/actions/workflow/status/SparkBayes/pystores/ci.yml)](https://github.com/SparkBayes/pystores/actions)
[![PyPI version](https://img.shields.io/pypi/v/pystores.svg)](https://pypi.org/project/pystores/)
[![PyPI downloads](https://img.shields.io/pypi/dm/pystores.svg)](https://pypi.org/project/pystores/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)

---

## 为什么用 pystores？

用 Python 构建交互式 Web 应用（NiceGUI、Streamlit、Reflex…）很愉快——直到状态管理成为现实问题。当第二个用户连上来时，三个问题立刻浮现：

| 问题 | 痛点 |
|------|------|
| **多用户状态混用** | 服务端 UI 运行在单一共享进程，一个模块级变量被*所有*用户共享 |
| **服务调用样板代码** | 每个操作都要处理加载态、token 注入、错误处理、结果合并——每个 30~50 行 |
| **散落的副作用** | "登录后加载资料"最终变成散落在各处的命令式调用 |

pystores 全部声明式解决——而且核心**与 UI 框架无关**，你的状态层比任何当下选择的 UI 框架都活得久。

## 功能特性

| 能力 | 说明 |
|------|------|
| **三级隔离** | `tab` / `browser` / `client` 上下文——每个连接拥有独立的状态实例 |
| **声明式 Action** | 10 行配置自动生成服务调用方法（加载态/token/错误/结果全处理） |
| **响应式副作用** | `STATE_MONITORS`——声明字段变化后要发生什么，框架自动编排 |
| **安全跨状态访问** | 基于白名单的 `get_state_value`——只共享你声明的内容 |
| **状态持久化** | 声明 `_state_storage_field` 即自动刷新安全存储 |
| **生命周期管理** | 实例自动创建/销毁，`_before_dispose` 钩子清理——杜绝内存泄漏 |

## 安装

```bash
pip install "pystores[nicegui]"
```

核心（`pystores.core`）**零依赖**，无需 NiceGUI 也能独立运行。

## 快速开始（NiceGUI）

```python
from typing import ClassVar

from nicegui import ui
from nicegui.binding import bindable_dataclass

from pystores import NiceGUIStore, nicegui_backend

# 1. 注入 NiceGUI 后端（上下文 + 存储）
nicegui_backend()


# 2. 定义状态
@bindable_dataclass
class Counter(NiceGUIStore):
    _state_name: ClassVar[str] = "counter"
    count: int = 0


# 3. 响应式绑定 UI
@ui.page("/")
async def index() -> None:
    state = await Counter.get_instance()
    ui.label().bind_text_from(state, "count")
    ui.button("+1", on_click=lambda: state.update({"count": state.count + 1}))


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="127.0.0.1", port=8080, storage_secret="pystores-secret")
```

打开两个浏览器标签页——各自**独立的计数**。刷新——计数**依然保留**。

## 示例

运行任一示例体验框架能力（`python examples/<name>/main.py`）：

| 示例 | 演示内容 | 运行 |
|------|---------|------|
| [`01_quickstart`](examples/01_quickstart/main.py) | 响应式绑定、隔离、持久化 | `:8080` |
| [`02_todo_app`](examples/02_todo_app/main.py) | 多用户 Todo——声明式 CRUD、跨状态引用、白名单、StoreManager、STATE_MONITORS | `:8081` |
| [`03_agnostic`](examples/03_agnostic/main.py) | **纯核心 CLI**——完全不依赖 NiceGUI | CLI |
| [`04_auth`](examples/04_auth/main.py) | 声明式认证——自动 token 注入、生命周期 + `_before_dispose` | `:8083`（密码 `123456`） |
| [`05_custom_providers`](examples/05_custom_providers/main.py) | 三个协议全部自定义（Context/Storage/Service） | CLI |

## 架构

```
┌────────────────────────────────────────────────────────────┐
│  你的应用 — 状态 + UI                                        │
├────────────────────────────────────────────────────────────┤
│  pystores.core            （框架无关，零依赖）               │
│    BaseStore · StoreManager · StateHookManager · Result    │
│                                                             │
│    ┌───────────────────────────────────────────┐           │
│    │  BaseStore.configure(context=, storage=,  │           │
│    │                     service=)             │           │
│    └──────┬──────────────┬─────────────┬───────┘           │
│           │              │             │                    │
│   ContextProvider  StorageProvider  ServiceExecutor        │
│           │              │             │                    │
│           └──────────────┴─────────────┴────────┘           │
├────────────────────────────────────────────────────────────┤
│  pystores.backends.nicegui  （可插拔适配器）                 │
│    NiceGUIContext · NiceGUIStorage · NiceGUIStore          │
│    （ui.context IDs · app.storage · bindable_dataclass）    │
└────────────────────────────────────────────────────────────┘
```

核心只认识三个小协议，NiceGUI 后端实现它们。**把它们指向 Streamlit、Reflex 或你自己的层——核心零改动。**

## 文档

- 每个示例都是自包含、可运行的课程（见 [示例](#示例)）。
- 按 `01 → 05` 顺序过一遍即可掌握全部核心概念。

## 许可证

[MIT](LICENSE) © SparkBayes
