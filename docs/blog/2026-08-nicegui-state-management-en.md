# State Management for Server-Side Python UI: Multi-User Isolation, Declarative Actions, and pystores

> Server-side UI frameworks (NiceGUI, Streamlit, Reflex) make pages easy and state hard — especially once a second user connects. This post shares a state-management approach hardened over a year in production, released as the open-source library **pystores**.

---

## The trap of server-side UI

NiceGUI's model is seductive: you write Python, the browser renders. No front-end/back-end split, no API layer, no state-management library — a single `@ui.page` gives you an interactive page.

But that "page-level state" only holds for a single user on a single connection. The moment two browsers open your app, the Python process is shared. A casually-written module-level variable becomes everyone's shared variable.

## Pain #1: Multi-user state bleed

Take a counter:

```python
count = 0  # module-level variable

@ui.page("/")
def page():
    ui.label().bind_text_from(...)  # shows count
```

User A clicks ten times; user B opens the page and sees 10. Both users are fighting over one Python variable.

The fix isn't "be careful with globals" — it's **one state instance per connection**. pystores gives you three isolation levels to choose from:

```python
class CartState(NiceGUIStore):      # tab level: independent cart per tab
    _state_isolation_level = "tab"

class SessionState(NiceGUIStore):   # browser level: shared login across tabs
    _state_isolation_level = "browser"

class UserState(NiceGUIStore):      # client level: default, per connection
    _state_isolation_level = "client"
```

Underneath is a nested dict `{context_id: {state_name: instance}}` with O(1) lookups. Isolation IDs come from NiceGUI's connection system (`tab_id` / `browser_id` / `client_id`) — three tabs in one browser get three carts and one login, **physically isolated, with zero hand-written conditionals**.

## Pain #2: Service-call boilerplate

Every real-world state operation looks like this (30–50 lines):

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

Twenty store classes × five operations each = a hundred near-identical methods. Change one pattern, change a hundred places.

pystores replaces this with **declarative configuration** — 10 lines of config, and the method is generated for you:

```python
class OrderStore(NiceGUIStore):
    _state_action_methods = {
        "fetch_orders": {
            "service_name": "order",
            "method_name": "list",
            "params_mapping": {"page": "page", "user_id": "user.id"},  # cross-store params
            "requires_token": True,      # token injected automatically
            "refresh": True,             # is_loading managed automatically
            "result_field": "orders",    # service result written into state
        },
    }
```

The framework handles: fetching the token → resolving params (including cross-store references like `user.id`) → calling the service → handling errors → merging the result → managing the loading flag → refreshing the UI. **You declare what to do, not how.**

## Pain #3: Scattered side-effects

"What should happen after login?" Initialize the SSE connection, bind the device, push the token, fetch unread messages… If these live as imperative calls inside the login handler, adding a step means hunting through the codebase.

pystores centralizes them into one declarative mapping:

```python
BaseStore.set_monitors({
    "user": {
        "is_authenticated": {
            True: [
                {"state": "notification", "method": "init_sse", "params": {"token": "user.token"}},
                {"state": "device",       "method": "bind_device", "params": {}},
                {"state": "todo",         "method": "fetch_todos", "params": {}},
            ],
            False: [  # logout: clean up + dispose
                {"state": "notification", "method": "disconnect_sse", "params": {}},
            ],
        }
    }
})
```

The moment `user.is_authenticated` flips from `False` to `True`, those three actions fire in sequence. Adding logic = adding one row to the table, never touching business code.

## Lifecycle and persistence, handled

- **Lifecycle**: instances auto-create, `dispose_instance()` destroys, `_before_dispose` hooks clean up — no memory leaks in multi-user apps.
- **Persistence**: declare fields and storage is automatic:

```python
class UserState(NiceGUIStore):
    _state_storage_field = {"refresh_token": "user"}  # login survives page refresh
```

## Quickstart: running in 30 seconds

```bash
pip install "pystores[nicegui]"
```

```python
from typing import ClassVar
from nicegui import ui
from nicegui.binding import bindable_dataclass
from pystores import NiceGUIStore, nicegui_backend

nicegui_backend()  # inject the NiceGUI backend

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

Open two tabs — the counters are independent. Refresh — the count survives.

## Architecture: a core decoupled from the framework

pystores makes one counterintuitive choice: **the core (`pystores.core`) does not depend on any UI framework**.

State management rests on just three small protocols:

```
ContextProvider   — where isolation IDs come from
StorageProvider   — where state is persisted
ServiceExecutor   — where service calls go
```

NiceGUI is just one implementation of these protocols (`backends.nicegui`). Which means:

- Use NiceGUI today, switch to Streamlit / Reflex tomorrow — **your core and business stores change nothing**;
- Your state layer outlives whichever UI framework you pick.

## Closing

This is not a toy. It has served 29 domain stores in a production system for nearly a year, and the hard-won lessons (closure capture, dataclass defaults, framework quirks without a UI context) are fixed and locked in as tests.

If you're building a medium-complexity app with NiceGUI, give it a try:

- **GitHub**: https://github.com/SparkBayes/pystores
- **PyPI**: `pip install "pystores[nicegui]"`
- **Examples**: five runnable apps in the repo's `examples/` (quickstart / multi-user Todo / declarative auth / custom providers / a pure-core CLI with no UI framework)

> Cover image: pystores architecture diagram (see README)
