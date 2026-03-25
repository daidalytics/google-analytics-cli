"""Pagination helpers.

Provides both:
- paginate_all(): API-level pagination (fetches all pages from Google API)
- paginate(): Client-side pagination (slices a local list for display)

Equivalent to GTM CLI's pagination.ts + paginateAll() in client.ts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from ..config.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar("T")


def paginate_all(
    list_fn: Callable[..., Any],
    result_key: str,
    **kwargs: Any,
) -> list:
    """Paginate through all results from a Google API list operation.

    Args:
        list_fn: The API list method (e.g., admin.accounts().list)
        result_key: The key in the response containing the items array
        **kwargs: Additional arguments to pass to the list method

    Returns:
        All items across all pages.

    Usage:
        accounts = paginate_all(
            lambda **kw: admin.accounts().list(**kw).execute(),
            "accounts",
            pageSize=200,
        )
    """
    all_results = []
    page_token = None

    while True:
        if page_token:
            kwargs["pageToken"] = page_token

        response = list_fn(**kwargs)
        items = response.get(result_key, [])
        all_results.extend(items)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_results


@dataclass
class PaginatedResult:
    """Result of client-side pagination."""
    items: list
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next_page: bool
    has_prev_page: bool


def paginate(items: list, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> PaginatedResult:
    """Client-side pagination of a local list.

    Equivalent to GTM CLI's paginate() in pagination.ts.
    """
    page = max(1, page)
    page_size = min(MAX_PAGE_SIZE, max(1, page_size))

    total_items = len(items)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = min(start + page_size, total_items)

    return PaginatedResult(
        items=items[start:end],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next_page=page < total_pages,
        has_prev_page=page > 1,
    )
