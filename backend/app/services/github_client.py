"""Raw GitHub API calls. All methods take explicit token — no shared session state.

Raises ``GitHubApiError`` on non-2xx responses from the GitHub API.
Callers should catch this and return appropriate HTTP responses.
"""

import base64
import logging

import httpx

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


class GitHubApiError(Exception):
    """Raised when the GitHub API returns a non-2xx status."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API {status_code}: {message}")


def _check(resp: httpx.Response) -> None:
    """Raise ``GitHubApiError`` on non-2xx responses."""
    if resp.is_success:
        return
    try:
        body = resp.json()
        msg = body.get("message", resp.reason_phrase or "Unknown error")
    except Exception:
        msg = resp.reason_phrase or "Unknown error"
    raise GitHubApiError(resp.status_code, msg)


class GitHubClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

    async def get_user(self, token: str) -> dict:
        resp = await self._client.get(f"{GITHUB_API}/user", headers=self._headers(token))
        _check(resp)
        return resp.json()

    async def list_repos(self, token: str, per_page: int = 30, page: int = 1) -> list[dict]:
        resp = await self._client.get(
            f"{GITHUB_API}/user/repos",
            headers=self._headers(token),
            params={"per_page": per_page, "page": page, "sort": "updated"},
        )
        _check(resp)
        return resp.json()

    async def get_repo(self, token: str, full_name: str) -> dict:
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{full_name}", headers=self._headers(token)
        )
        _check(resp)
        return resp.json()

    async def get_branch(self, token: str, full_name: str, branch: str) -> dict:
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{full_name}/branches/{branch}",
            headers=self._headers(token),
        )
        _check(resp)
        return resp.json()

    async def get_branch_head_sha(self, token: str, full_name: str, branch: str) -> str:
        data = await self.get_branch(token, full_name, branch)
        return data["commit"]["sha"]

    async def get_tree(self, token: str, full_name: str, branch: str) -> list[dict]:
        """Fetch the recursive tree for a branch. Returns only blob entries.

        Thin wrapper over :meth:`get_tree_with_cache` for callers that don't
        care about ETag/caching semantics. Always hits the network.
        """
        tree, _etag = await self.get_tree_with_cache(token, full_name, branch)
        return tree or []

    async def get_tree_with_cache(
        self,
        token: str,
        full_name: str,
        branch: str,
        *,
        etag: str | None = None,
    ) -> tuple[list[dict] | None, str | None]:
        """Fetch the recursive tree with conditional-request support.

        Sends ``If-None-Match: <etag>`` when ``etag`` is provided. Returns
        ``(tree, new_etag)`` on 200 and ``(None, etag)`` on 304 Not Modified
        — the ``None`` sentinel tells the caller to reuse its cached tree.

        GitHub counts 304 responses as "no content served" for the primary
        rate limit (see GitHub REST API docs), so ETag-aware polling is the
        recommended pattern for repeated tree fetches.
        """
        headers = self._headers(token)
        if etag:
            headers["If-None-Match"] = etag
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{full_name}/git/trees/{branch}",
            headers=headers,
            params={"recursive": "1"},
        )
        if resp.status_code == 304:
            return None, etag
        _check(resp)
        new_etag = resp.headers.get("ETag")
        tree = [
            item
            for item in resp.json().get("tree", [])
            if item["type"] == "blob"
        ]
        return tree, new_etag

    async def list_branches(
        self, token: str, full_name: str, per_page: int = 50,
    ) -> list[dict]:
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{full_name}/branches",
            headers=self._headers(token),
            params={"per_page": per_page},
        )
        _check(resp)
        return resp.json()

    async def get_file_content(
        self, token: str, full_name: str, path: str, ref: str
    ) -> str | None:
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{full_name}/contents/{path}",
            headers=self._headers(token),
            params={"ref": ref},
        )
        if resp.status_code == 404:
            return None
        _check(resp)
        data = resp.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode(errors="replace")
        return data.get("content", "")

    async def get_release_by_tag(
        self, token: str, full_name: str, tag: str
    ) -> dict | None:
        """Fetch GitHub release info by tag name. Returns None on 404."""
        resp = await self._client.get(
            f"{GITHUB_API}/repos/{full_name}/releases/tags/{tag}",
            headers=self._headers(token),
        )
        if resp.status_code == 404:
            return None
        _check(resp)
        return resp.json()
