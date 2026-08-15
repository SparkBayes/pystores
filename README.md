# pystores

**Framework-agnostic state management for server-side Python UI.**

Declarative, multi-user-isolated stores for NiceGUI and any other server-side UI framework.

**English** | [简体中文](https://github.com/SparkBayes/pystores/blob/main/README_zh.md)

[![CI](https://img.shields.io/github/actions/workflow/status/SparkBayes/pystores/ci.yml)](https://github.com/SparkBayes/pystores/actions)
[![PyPI version](https://img.shields.io/pypi/v/pystores.svg)](https://pypi.org/project/pystores/)
[![PyPI downloads](https://img.shields.io/pypi/dm/pystores.svg)](https://pypi.org/project/pystores/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)

---

## Why pystores?

Building interactive web apps in Python (NiceGUI, Streamlit, Reflex, …) is pleasant — until state becomes real. Three problems show up the moment more than one user connects:

| Problem | Pain |
|---------|------|
| **Multi-user state bleed** | Server-side UI runs in one shared process. A naive module-level variable is shared by *every* user. |
| **Service-call boilerplate** | Every action needs loading-state handling, token injection, error handling, result merging — 30–50 lines each. |
| **Scattered side-effects** | "On login, load the profile" ends up as imperative calls sprinkled across handlers. |

pystores solves all three declaratively — and its core is **UI-framework-free**, so your state layer outlives any UI framework you choose today.

## Features

| Capability | Description |
|------------|-------------|
| **Three-level isolation** | `tab` / `browser` / `client` contexts — each connection gets its own store instances |
| **Declarative actions** | A 10-line config auto-generates service-call methods (loading, token, errors, result handled) |
| **Reactive side-effects** | `STATE_MONITORS` — describe what happens when a field changes, let the framework orchestrate |
| **Safe cross-store access** | Whitelist-based `get_state_value` — share only what you declare |
| **Persistence** | Declare `_state_storage_field` and refresh-safe storage is automatic |
| **Lifecycle management** | Instances auto-create / dispose with `_before_dispose` hooks — no memory leaks |

## Installation

```bash
pip install "pystores[nicegui]"
```

The core (`pystores.core`) has **zero dependencies** and works without NiceGUI.

## Quickstart (NiceGUI)

```python
from typing import ClassVar

from nicegui import ui
from nicegui.binding import bindable_dataclass

from pystores import NiceGUIStore, nicegui_backend

# 1. Inject the NiceGUI backend (context + storage)
nicegui_backend()


# 2. Define a store
@bindable_dataclass
class Counter(NiceGUIStore):
    _state_name: ClassVar[str] = "counter"
    count: int = 0


# 3. Bind the UI reactively
@ui.page("/")
async def index() -> None:
    state = await Counter.get_instance()
    ui.label().bind_text_from(state, "count")
    ui.button("+1", on_click=lambda: state.update({"count": state.count + 1}))


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(host="127.0.0.1", port=8080, storage_secret="pystores-secret")
```

Open two browser tabs — each has an **independent counter**. Refresh — the count **survives**.

## Examples

Run any example to see the framework in action (`python examples/<name>/main.py`):

| Example | Demo | Run |
|---------|------|-----|
| [`01_quickstart`](examples/01_quickstart/main.py) | Reactive binding, isolation, persistence | `:8080` |
| [`02_todo_app`](examples/02_todo_app/main.py) | Multi-user Todo — declarative CRUD, cross-store refs, whitelist, StoreManager, STATE_MONITORS | `:8081` |
| [`03_agnostic`](examples/03_agnostic/main.py) | **Pure core CLI** — no NiceGUI dependency at all | CLI |
| [`04_auth`](examples/04_auth/main.py) | Declarative auth — automatic token injection, lifecycle + `_before_dispose` | `:8083` (pwd `123456`) |
| [`05_custom_providers`](examples/05_custom_providers/main.py) | All three protocols replaced (Context/Storage/Service) | CLI |

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  Your App — stores + UI                                     │
├────────────────────────────────────────────────────────────┤
│  pystores.core            (framework-agnostic, zero deps)  │
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
│  pystores.backends.nicegui  (pluggable adapter)            │
│    NiceGUIContext · NiceGUIStorage · NiceGUIStore          │
│    (ui.context IDs · app.storage · bindable_dataclass)     │
└────────────────────────────────────────────────────────────┘
```

The core speaks three small protocols. The NiceGUI backend implements them. **Point them at Streamlit, Reflex, or your own layer — nothing in the core changes.**

## Documentation

- Each example is a self-contained, runnable lesson (see [Examples](#examples)).
- Working through `01 → 05` in order covers every core concept.

## License

[MIT](LICENSE) © SparkBayes
