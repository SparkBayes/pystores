"""pytest 全局配置 - 提供测试间状态隔离"""

import pytest

from pystores.core.base import BaseStore
from pystores.core.context import MemoryContext
from pystores.core.storage import MemoryStorage


@pytest.fixture(autouse=True)
def clean_store_state():
    """每个测试前重置 BaseStore 类级状态，避免测试间污染"""
    BaseStore._instances.clear()
    BaseStore.configure(
        context=MemoryContext(),
        storage=MemoryStorage(),
        service=None,
    )
    yield
    BaseStore._instances.clear()
