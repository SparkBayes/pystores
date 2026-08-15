# pystores

**Framework-agnostic, server-side UI state management for Python.**

> 面向服务端 UI（NiceGUI / Streamlit / Reflex 等）的结构化状态管理库，解决**多用户状态隔离**、**声明式服务调用**、**响应式副作用**三大痛点。

> **设计哲学**：核心层（`pystores.core`）零 UI 框架依赖，通过 `ContextProvider` / `StorageProvider` / `ServiceExecutor` 三个协议与任意框架解耦。当前提供 **NiceGUI 后端**，未来可平滑接入其他服务端 UI 框架。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **三级隔离** | tab / browser / client 三级上下文，杜绝多用户状态混用 |
| **声明式 Action** | 10 行配置代替 30-50 行样板代码，自动生成服务调用方法 |
| **声明式副作用** | 状态变化 → 自动级联触发动作（登录后初始化连接、登出清理等） |
| **生命周期管理** | 实例自动创建 / 销毁，杜绝内存泄漏 |
| **状态持久化** | 声明字段自动存储，页面刷新恢复 |
| **跨状态通信** | 白名单字段安全访问，避免强耦合 |

## 快速开始（NiceGUI）

```bash
pip install "pystores[nicegui]"
```

```python
from nicegui import ui
from pystores import NiceGUIStore, nicegui_backend

# 1. 注入后端
nicegui_backend.configure()

# 2. 定义状态
class Counter(NiceGUIStore):
    _state_name = "counter"
    count: int = 0

# 3. 绑定 UI
@ui.page("/")
def page():
    state = await Counter.get_instance()
    ui.label().bind_text_from(state, "count")
    ui.button("+1", on_click=lambda: state.update({"count": state.count + 1}))

ui.run()
```

## 安装与文档

- 完整文档见 [`docs/`](docs/)
- 示例见 [`examples/`](examples/)

## License

[MIT](LICENSE) © Zhang Di
