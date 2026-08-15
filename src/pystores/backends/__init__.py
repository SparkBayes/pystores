"""pystores.backends - 服务端 UI 框架适配器层

当前提供 NiceGUI 后端（backends.nicegui），未来可添加 Streamlit、Reflex 等。
核心层通过协议与后端解耦，新增后端只需实现 ContextProvider / StorageProvider。
"""
