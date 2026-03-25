"""Tests for ga_cli.utils.pagination."""


from ga_cli.config.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from ga_cli.utils.pagination import PaginatedResult, paginate, paginate_all


class TestPaginate:
    def test_first_page(self):
        items = list(range(100))
        result = paginate(items, page=1, page_size=10)
        assert result.items == list(range(10))
        assert result.page == 1
        assert result.page_size == 10
        assert result.total_items == 100
        assert result.total_pages == 10
        assert result.has_next_page is True
        assert result.has_prev_page is False

    def test_middle_page(self):
        items = list(range(100))
        result = paginate(items, page=5, page_size=10)
        assert result.items == list(range(40, 50))
        assert result.has_next_page is True
        assert result.has_prev_page is True

    def test_last_page(self):
        items = list(range(100))
        result = paginate(items, page=10, page_size=10)
        assert result.items == list(range(90, 100))
        assert result.has_next_page is False
        assert result.has_prev_page is True

    def test_partial_last_page(self):
        items = list(range(15))
        result = paginate(items, page=2, page_size=10)
        assert result.items == list(range(10, 15))
        assert result.total_pages == 2
        assert result.has_next_page is False

    def test_empty_list(self):
        result = paginate([], page=1, page_size=10)
        assert result.items == []
        assert result.total_items == 0
        assert result.total_pages == 1
        assert result.has_next_page is False
        assert result.has_prev_page is False

    def test_page_beyond_range(self):
        items = list(range(10))
        result = paginate(items, page=999, page_size=10)
        assert result.items == []
        assert result.page == 999

    def test_negative_page_clamped_to_1(self):
        items = list(range(10))
        result = paginate(items, page=-5, page_size=10)
        assert result.page == 1

    def test_page_size_capped_at_max(self):
        items = list(range(500))
        result = paginate(items, page=1, page_size=9999)
        assert result.page_size == MAX_PAGE_SIZE

    def test_page_size_minimum_is_1(self):
        items = list(range(10))
        result = paginate(items, page=1, page_size=0)
        assert result.page_size == 1

    def test_default_page_size(self):
        items = list(range(100))
        result = paginate(items)
        assert result.page_size == DEFAULT_PAGE_SIZE


class TestPaginateAll:
    def test_single_page(self):
        def mock_list_fn(**kwargs):
            return {"items": [{"id": 1}, {"id": 2}]}

        result = paginate_all(mock_list_fn, "items")
        assert result == [{"id": 1}, {"id": 2}]

    def test_multiple_pages(self):
        call_count = 0

        def mock_list_fn(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "accounts": [{"id": 1}, {"id": 2}],
                    "nextPageToken": "token_2",
                }
            elif call_count == 2:
                return {
                    "accounts": [{"id": 3}],
                    "nextPageToken": "token_3",
                }
            else:
                return {
                    "accounts": [{"id": 4}],
                }

        result = paginate_all(mock_list_fn, "accounts")
        assert len(result) == 4
        assert result == [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]

    def test_empty_response(self):
        def mock_list_fn(**kwargs):
            return {"items": []}

        result = paginate_all(mock_list_fn, "items")
        assert result == []

    def test_missing_result_key(self):
        def mock_list_fn(**kwargs):
            return {"other_key": [{"id": 1}]}

        result = paginate_all(mock_list_fn, "items")
        assert result == []

    def test_passes_kwargs(self):
        received_kwargs = {}

        def mock_list_fn(**kwargs):
            received_kwargs.update(kwargs)
            return {"items": [{"id": 1}]}

        paginate_all(mock_list_fn, "items", pageSize=200, filter="test")
        assert received_kwargs["pageSize"] == 200
        assert received_kwargs["filter"] == "test"

    def test_page_token_passed_on_subsequent_calls(self):
        calls = []

        def mock_list_fn(**kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return {"items": [{"id": 1}], "nextPageToken": "abc"}
            return {"items": [{"id": 2}]}

        paginate_all(mock_list_fn, "items")
        assert "pageToken" not in calls[0]
        assert calls[1]["pageToken"] == "abc"


class TestPaginatedResult:
    def test_dataclass_fields(self):
        result = PaginatedResult(
            items=[1, 2, 3],
            page=1,
            page_size=10,
            total_items=3,
            total_pages=1,
            has_next_page=False,
            has_prev_page=False,
        )
        assert result.items == [1, 2, 3]
        assert result.page == 1
        assert result.total_pages == 1
