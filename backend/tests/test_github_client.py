from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.github_client import GitHubClient


def make_mock_response(status_code=200, json_data=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    def raise_for_status():
        if status_code >= 400:
            raise Exception("HTTP Error")
    mock_resp.raise_for_status.side_effect = raise_for_status
    return mock_resp

@pytest.fixture
def mock_httpx_client():
    client = AsyncMock()
    return client

@pytest.fixture
def github_client(mock_httpx_client):
    return GitHubClient(http_client=mock_httpx_client)

@pytest.mark.asyncio
async def test_get_user(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(200, {"login": "testuser"})
    res = await github_client.get_user("fake_token")
    assert res == {"login": "testuser"}

@pytest.mark.asyncio
async def test_list_repos(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(200, [{"name": "repo1"}])
    res = await github_client.list_repos("fake_token", per_page=10, page=2)
    assert res == [{"name": "repo1"}]

@pytest.mark.asyncio
async def test_get_repo(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(200, {"name": "repo1"})
    res = await github_client.get_repo("fake_token", "user/repo1")
    assert res == {"name": "repo1"}

@pytest.mark.asyncio
async def test_get_branch_and_sha(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(200, {"commit": {"sha": "1234abcd"}})
    res = await github_client.get_branch("fake_token", "user/repo1", "main")
    assert res == {"commit": {"sha": "1234abcd"}}

    sha = await github_client.get_branch_head_sha("fake_token", "user/repo1", "main")
    assert sha == "1234abcd"

@pytest.mark.asyncio
async def test_get_tree(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(200, {
        "tree": [
            {"type": "blob", "path": "file1"},
            {"type": "tree", "path": "dir1"},
        ]
    })
    res = await github_client.get_tree("fake_token", "user/repo1", "main")
    assert res == [{"type": "blob", "path": "file1"}]

@pytest.mark.asyncio
async def test_get_tree_with_cache_200_returns_tree_and_etag(github_client, mock_httpx_client):
    """On 200, returns (tree, new_etag) and exposes the server's ETag for
    later If-None-Match reuse.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.headers = {"ETag": 'W/"abc123"'}
    mock_resp.json.return_value = {
        "tree": [
            {"type": "blob", "path": "src/a.py"},
            {"type": "tree", "path": "src"},
        ]
    }
    mock_httpx_client.get.return_value = mock_resp

    tree, etag = await github_client.get_tree_with_cache(
        "fake_token", "user/repo1", "main",
    )

    assert tree == [{"type": "blob", "path": "src/a.py"}]
    assert etag == 'W/"abc123"'


@pytest.mark.asyncio
async def test_get_tree_with_cache_304_returns_none(github_client, mock_httpx_client):
    """On 304 Not Modified, returns (None, provided_etag) signalling the
    caller to use its cached tree. Sends If-None-Match when etag given.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 304
    mock_resp.is_success = False
    mock_resp.headers = {}
    mock_httpx_client.get.return_value = mock_resp

    tree, etag = await github_client.get_tree_with_cache(
        "fake_token", "user/repo1", "main", etag='W/"abc123"',
    )

    assert tree is None
    assert etag == 'W/"abc123"'
    # Verify If-None-Match header was sent
    call_kwargs = mock_httpx_client.get.call_args.kwargs
    assert call_kwargs["headers"].get("If-None-Match") == 'W/"abc123"'


@pytest.mark.asyncio
async def test_get_tree_with_cache_no_etag_sends_no_if_none_match(
    github_client, mock_httpx_client,
):
    """When caller passes no etag, no If-None-Match header is sent — always
    returns a full tree on success.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.headers = {"ETag": 'W/"xyz"'}
    mock_resp.json.return_value = {"tree": []}
    mock_httpx_client.get.return_value = mock_resp

    tree, etag = await github_client.get_tree_with_cache(
        "fake_token", "user/repo1", "main",
    )

    assert tree == []
    assert etag == 'W/"xyz"'
    call_kwargs = mock_httpx_client.get.call_args.kwargs
    assert "If-None-Match" not in call_kwargs["headers"]


@pytest.mark.asyncio
async def test_get_tree_delegates_to_get_tree_with_cache(
    github_client, mock_httpx_client,
):
    """Legacy `get_tree()` returns just the list — it is now a thin wrapper
    around `get_tree_with_cache()` but preserves the existing contract.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.headers = {"ETag": 'W/"qqq"'}
    mock_resp.json.return_value = {
        "tree": [{"type": "blob", "path": "only.py"}],
    }
    mock_httpx_client.get.return_value = mock_resp

    tree = await github_client.get_tree("fake_token", "user/repo1", "main")
    assert tree == [{"type": "blob", "path": "only.py"}]


@pytest.mark.asyncio
async def test_get_file_content_404(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(404)
    res = await github_client.get_file_content("fake_token", "user/repo1", "path/to/file", "main")
    assert res is None

@pytest.mark.asyncio
async def test_get_file_content_base64(github_client, mock_httpx_client):
    import base64
    content = base64.b64encode(b"hello world").decode('ascii')
    mock_httpx_client.get.return_value = make_mock_response(200, {"encoding": "base64", "content": content})
    res = await github_client.get_file_content("fake_token", "user/repo1", "path/to/file", "main")
    assert res == "hello world"

@pytest.mark.asyncio
async def test_get_file_content_plain(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(200, {"encoding": "plain", "content": "plain text"})
    res = await github_client.get_file_content("fake_token", "user/repo1", "path/to/file", "main")
    assert res == "plain text"

@pytest.mark.asyncio
async def test_get_file_content_no_encoding(github_client, mock_httpx_client):
    mock_httpx_client.get.return_value = make_mock_response(200, {"content": "default text"})
    res = await github_client.get_file_content("fake_token", "user/repo1", "path/to/file", "main")
    assert res == "default text"
