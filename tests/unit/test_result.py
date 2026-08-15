"""Result 与 handle_exceptions 的单元测试"""

from pystores.result import Result, handle_exceptions


class TestResult:
    def test_create_success(self):
        result = Result.create_success(42)
        assert result.success is True
        assert result.data == 42
        assert result.is_success()
        assert not result.is_failure()

    def test_create_failure(self):
        result = Result.create_failure("SOME_ERROR", "出错了")
        assert result.success is False
        assert result.code == "SOME_ERROR"
        assert result.message == "出错了"
        assert result.is_failure()

    def test_to_dict(self):
        result = Result.create_success({"a": 1}, message="OK", code="0")
        data = result.to_dict()
        assert data["code"] == "0"
        assert data["msg"] == "OK"
        assert data["data"] == {"a": 1}


class TestHandleExceptions:
    async def test_async_wrapper_returns_result_on_error(self):
        @handle_exceptions("测试操作")
        async def boom():
            raise ValueError("bad")

        result = await boom()
        assert result.success is False
        assert result.code == "ExceptionOccurred"

    def test_sync_wrapper_returns_result_on_error(self):
        @handle_exceptions("测试操作")
        def boom():
            raise ValueError("bad")

        result = boom()
        assert result.success is False

    async def test_success_path_passthrough(self):
        @handle_exceptions("测试操作")
        async def ok():
            return Result.create_success(1)

        result = await ok()
        assert result.success is True
