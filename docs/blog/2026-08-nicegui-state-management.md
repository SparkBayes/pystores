# NiceGUI 多用户状态管理实践：三个痛点与一套声明式解法

> 用 Python 写服务端 UI（NiceGUI / Streamlit / Reflex），页面很好写，状态很难管。尤其是当第二个用户连上来之后。
> 这篇文章分享一套在实战中打磨了一年的状态管理方案，以及它如何以开源库 **pystores** 的形式落地。

---

## 引子：服务端 UI 的诱惑与陷阱

NiceGUI 这类服务端 UI 框架的体验很特别：你写的是 Python，渲染在浏览器。没有前后端分离、没有 API 层、没有状态管理库——代码里一个 `@ui.page` 就能出一个交互页面。

但这有个隐含前提：**"页面级状态"只在单用户、单连接时成立**。

一旦两个浏览器同时打开你的应用，Python 进程是共享的。你随手写的模块级变量，就是所有用户共用的"公共厕所"。这就是服务端 UI 的第一道坎。

## 痛点一：多用户状态混用

想象一个计数器应用：

```python
count = 0  # 模块级变量

@ui.page("/")
def page():
    ui.label().bind_text_from(...)  # 显示 count
```

用户 A 点了 10 次，用户 B 打开页面看到的就是 10。两个用户的状态在同一个 Python 变量里打架。

解法不是"小心点别用全局变量"——而是**给每个连接一份独立的状态实例**。

pystores 把隔离分成三级，你按业务需要声明：

```python
class CartState(NiceGUIStore):      # 标签页级：每个 tab 独立的购物车
    _state_isolation_level = "tab"

class SessionState(NiceGUIStore):   # 浏览器级：跨 tab 共享的登录态
    _state_isolation_level = "browser"

class UserState(NiceGUIStore):      # 客户端级：默认，连接维度
    _state_isolation_level = "client"
```

底层是一个双层字典 `{context_id: {state_name: instance}}`，`get_instance()` 用 O(1) 查找。隔离 ID 来自 NiceGUI 的连接体系（`tab_id` / `browser_id` / `client_id`），同一个浏览器开 3 个标签页，就是 3 份购物车、1 份登录态——**物理隔离，不用你手写一个 if**。

## 痛点二：服务调用的样板代码

真实应用里，每个状态操作长这样（30~50 行）：

```python
async def fetch_orders(self, page):
    self.is_loading = True
    try:
        token = await UserState.get_instance().token
        result = await order_service.list(token=token, page=page)
        if result.success:
            await self.update(result.data, refresh=True)
        return result
    except Exception as e:
        return Result.create_failure("FetchFailed", str(e))
    finally:
        self.is_loading = False
```

20 个状态类、每个 5 个操作，就是 100 份几乎一样的代码。改一个模式，改 100 处。

pystores 用**声明式配置**替代：10 行配置，方法自动生成。

```python
class OrderStore(NiceGUIStore):
    _state_action_methods = {
        "fetch_orders": {
            "service_name": "order",
            "method_name": "list",
            "params_mapping": {"page": "page", "user_id": "user.id"},  # 跨状态取参
            "requires_token": True,      # token 自动注入
            "refresh": True,             # is_loading 自动管理
            "result_field": "orders",    # 服务结果写入状态字段
        },
    }
```

框架自动帮你完成：取 token → 解析参数（含跨状态引用 `user.id`）→ 调服务 → 处理错误 → 合并结果 → 管理 loading → 刷新 UI。**你只声明"做什么"，不写"怎么做"**。

## 痛点三：散落的副作用

"登录成功后要干什么"？初始化 SSE 连接、绑定设备、推送 token、拉未读消息……如果散落在登录方法里手动调用，新同事加一个步骤就要翻遍代码找登录处。

pystores 把它集中成一张声明式映射表：

```python
BaseStore.set_monitors({
    "user": {
        "is_authenticated": {
            True: [
                {"state": "notification", "method": "init_sse", "params": {"token": "user.token"}},
                {"state": "device",       "method": "bind_device", "params": {}},
                {"state": "todo",         "method": "fetch_todos", "params": {}},
            ],
            False: [  # 登出：清理 + 销毁
                {"state": "notification", "method": "disconnect_sse", "params": {}},
            ],
        }
    }
})
```

**登录态一变化，动作自动级联**——`user.is_authenticated` 从 `False` 变 `True` 的瞬间，这三件事按配置执行。新增逻辑 = 往表里加一行，不碰任何业务代码。

## 生命周期与持久化，顺手也解决了

- **生命周期**：实例自动创建、`dispose_instance()` 销毁、`_before_dispose` 钩子做清理，杜绝多用户场景的内存泄漏。
- **持久化**：声明字段即自动存取：

```python
class UserState(NiceGUIStore):
    _state_storage_field = {"refresh_token": "user"}  # 刷新页面不丢登录态
```

## 快速开始：30 秒跑起来

```bash
pip install "pystores[nicegui]"
```

```python
from typing import ClassVar
from nicegui import ui
from nicegui.binding import bindable_dataclass
from pystores import NiceGUIStore, nicegui_backend

nicegui_backend()  # 注入 NiceGUI 后端

@bindable_dataclass
class Counter(NiceGUIStore):
    _state_name: ClassVar[str] = "counter"
    count: int = 0

@ui.page("/")
async def index():
    state = await Counter.get_instance()
    ui.label().bind_text_from(state, "count")
    ui.button("+1", on_click=lambda: state.update({"count": state.count + 1}))

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="127.0.0.1", port=8080, storage_secret="secret")
```

打开两个标签页——计数各自独立。刷新——计数还在。

## 架构：核心与框架解耦

pystores 的设计有一个"反直觉"的决定：**核心层（`pystores.core`）不依赖任何 UI 框架**。

状态管理只依赖三个小协议：

```
ContextProvider   —— 三级隔离 ID 从哪来
StorageProvider   —— 状态存到哪
ServiceExecutor   —— 服务调用走哪
```

NiceGUI 只是这三个协议的其中一个实现（`backends.nicegui`）。这意味着：

- 今天用 NiceGUI，明天换 Streamlit / Reflex，**核心和你的业务状态零改动**；
- 你的状态层比 UI 框架活得久。

## 写在最后

这套方案不是纸上谈兵——它在生产项目里服务了 29 个领域状态、跑了近一年，踩过的坑（闭包捕获、dataclass 默认值、无 UI 上下文时的框架差异）都已经修掉并固化成测试。

如果你也在用 NiceGUI 构建中复杂度应用，欢迎试试：

- **GitHub**: https://github.com/SparkBayes/pystores
- **PyPI**: `pip install "pystores[nicegui]"`
- **示例**: 仓库 `examples/` 下有 5 个可运行示例（快速开始 / 多用户 Todo / 声明式认证 / 自定义 Provider / 无 UI 框架纯核心）

> 题图：pystores 架构图（见 README）
