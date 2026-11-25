# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""GitHub for Moody: the GitHub App a user connects their repositories through, the OAuth App that reads Epic's
packages, and the API calls made with each.

**The GitHub App.** "Connect GitHub" is the app's user authorization: the
control plane sends the user to GitHub's authorization page with the app's
client ID and a `state` it signed, GitHub sends them back to the callback with
a code, and the control plane trades the code for a user access token with the
app's client secret. A GitHub App asks for no scopes: what its token reaches is
the app's permissions (repository Contents, read and write, and Metadata,
read) on the repositories the app is installed on, cut down to what the user
can reach there. The repositories a user can pick are therefore the ones of the
installations their token lists (`installations`, `installation_repositories`);
a repository of an organization that has not installed the app is missing
until someone installs it there, from the app's installation page
(`install_url`), which a member who may not install it themselves sends to the
organization's owners as a request.

The app's user tokens expire after eight hours and come with a refresh token
that lasts six months (`Grant`); a refresh (`refresh`) returns a new pair and
retires the old one, so the service refreshes a token only when it is about to
expire, and stores the pair it got before using it (`Sessions.github_token`).

**The Epic connection.** Pulling the user's own copy of Unreal Engine from
`ghcr.io/epicgames/unreal-engine` takes a token that reads packages wherever the
account may, which a GitHub App's token cannot: the app is not installed on
EpicGames. That is a small OAuth App of its own that asks for `read:packages`
alone (`EPIC_SCOPE`). Whether the account is linked to Epic is the registry's
own answer (`registry_pull`): the token service of `ghcr.io` grants a pull of
Epic's image only to an account Epic linked, and refuses the rest.

**Both flows' state.** Each callback carries no credential of the user's own,
being a redirect from GitHub, so the state is what says whom the grant is for:
it names the user, the page to return to, and an expiry, under an HMAC keyed by
`MOODY_SECRET_KEY` and the flow it belongs to (`sign_state`, `read_state`), so
a state of one flow is no state of the other. A state nobody signed, or one
past its expiry, is refused before anything is exchanged, and the page it
names is never visited, which with the check that it lies under the site's own
address (`Sessions.site_page`) keeps either callback from redirecting anywhere
else.

Every token is stored only encrypted, with Fernet under a key derived from the
same secret (`seal`, `unseal`), and leaves the control plane only in requests
to GitHub and its registry, as the user's own registry credential for pulling
their copy of an app (`launcher.py`), and as the credential an engine clones
the project's repository with when it starts. Each key derived from the secret
is for one purpose, so a signed state can never be read as a sealed token or
the reverse.

A write names its branch (`GitHub.save`), on the read of what is there and on
the commit alike: the contents API commits to the repository's default branch
when none is named, and the default branch of a team's repository is the one
place Moody's agent must never write (`agent.py`, `tool_github_save`).

A repository's files are listed through the Git Trees API (`GitHub.files`),
recursive in one call where GitHub can, and walked a subtree at a time where
GitHub cuts the recursive listing short, which a game's repository of tens of
thousands of assets is large enough to make it do.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, NamedTuple
from urllib.parse import quote, urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"
APPS_URL = "https://github.com/apps"
# The container registry's token service, which answers whether an account may pull an image
REGISTRY_TOKEN_URL = "https://ghcr.io/token"
REGISTRY_SERVICE = "ghcr.io"
# What the Epic connection asks for, and the pull an account linked to Epic is granted
EPIC_SCOPE = "read:packages"
EPIC_PULL = "repository:epicgames/unreal-engine:pull"
# The two flows a signed state can belong to
GITHUB_FLOW = "github"
EPIC_FLOW = "epic"
STATE_SECONDS = 600
# Calls one listing of a repository's files may make, at most: a walk of a vast tree stops there
TREE_CALLS = 200
# What GitHub lists per page at most
PAGE_SIZE = 100


class Grant(NamedTuple):
    """What GitHub granted for an authorization or a refresh.

    `expires_in` and `refresh_token_expires_in` are seconds from the grant, and
    are absent, with `refresh_token`, for a token that does not expire: an
    OAuth App's, or a GitHub App's with expiring tokens switched off.
    """

    token: str
    scope: str
    expires_in: int | None = None
    refresh_token: str | None = None
    refresh_token_expires_in: int | None = None


class GitHubError(Exception):
    """A call GitHub refused, with its status and what it said."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _key(secret: str, purpose: str) -> bytes:
    """A key for one purpose, derived from the deployment's secret."""
    return hmac.new(secret.encode(), f"moody {purpose}".encode(), hashlib.sha256).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_state(secret: str, user_id: str, return_to: str, now: float | None = None, flow: str = GITHUB_FLOW) -> str:
    """The `state` of an authorization of one flow: the user and the page to return to, expiring, under an HMAC."""
    payload = {
        "u": user_id,
        "r": return_to,
        "e": int((now if now is not None else time.time()) + STATE_SECONDS),
        "n": secrets.token_urlsafe(8),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    mac = hmac.new(_key(secret, f"{flow} state"), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(mac)}"


def read_state(secret: str, state: str, now: float | None = None, flow: str = GITHUB_FLOW) -> dict[str, Any] | None:
    """What a `state` says, or nothing where it was not signed for this flow with the secret, is malformed, or expired."""
    body, _, mac = state.partition(".")
    if not body or not mac or not secret:
        return None
    expected = hmac.new(_key(secret, f"{flow} state"), body.encode(), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(expected, _unb64(mac)):
            return None
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("u"), str) or not isinstance(payload.get("r"), str):
        return None
    if not isinstance(payload.get("e"), int) or payload["e"] < (now if now is not None else time.time()):
        return None
    return payload


def seal(secret: str, token: str) -> str:
    """A token encrypted for storage."""
    return Fernet(base64.urlsafe_b64encode(_key(secret, "github token"))).encrypt(token.encode()).decode()


def unseal(secret: str, sealed: str) -> str | None:
    """A stored token decrypted, or nothing where the secret it was sealed under has changed."""
    try:
        return Fernet(base64.urlsafe_b64encode(_key(secret, "github token"))).decrypt(sealed.encode()).decode()
    except InvalidToken:
        return None


def seconds(value: Any) -> int | None:
    """A lifetime GitHub sent, in seconds, or nothing where it sent none."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class GitHub:
    """GitHub's OAuth endpoints, its REST API, and its container registry's token service, as far as Moody uses them.

    Every call raises `GitHubError` with GitHub's own message where GitHub
    refuses, so the service can say why to the user.
    """

    def __init__(self) -> None:
        self.http = httpx.Client(timeout=20, headers={"Accept": "application/vnd.github+json"})

    def _call(self, method: str, url: str, token: str, **kwargs: Any) -> Any:
        response = self.http.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"},
            **kwargs,
        )
        if response.status_code >= 400:
            try:
                message = response.json().get("message", "")
            except ValueError:
                message = response.text[:200]
            raise GitHubError(response.status_code, message or f"GitHub answered {response.status_code}")
        return response.json() if response.content else None

    def _pages(self, path: str, token: str, key: str, limit: int) -> list[dict[str, Any]]:
        """The items of a paginated listing that wraps them under `key`, up to `limit` of them."""
        items: list[dict[str, Any]] = []
        page = 1
        while len(items) < limit:
            body = self._call("GET", f"{API_URL}{path}", token, params={"per_page": PAGE_SIZE, "page": page})
            batch = body.get(key) or []
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            page += 1
        return items[:limit]

    @staticmethod
    def authorize_url(client_id: str, redirect_uri: str, state: str, scope: str | None = None) -> str:
        """The page that asks the user to authorize an app: the GitHub App with no scope, an OAuth App with `scope`."""
        query = {"client_id": client_id, "redirect_uri": redirect_uri, "state": state}
        if scope:
            query["scope"] = scope
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    @staticmethod
    def install_url(slug: str, state: str) -> str:
        """The GitHub App's installation page, where the user installs it on an account, or asks its owners to."""
        return f"{APPS_URL}/{quote(slug)}/installations/new?{urlencode({'state': state})}"

    def _grant(self, data: dict[str, str]) -> Grant:
        """POST to the token endpoint and read the grant, which GitHub refuses in the body as often as in the status."""
        response = self.http.post(TOKEN_URL, headers={"Accept": "application/json"}, data=data)
        try:
            body = response.json() if response.content else {}
        except ValueError:
            body = {}
        if response.status_code >= 400 or not body.get("access_token"):
            status = response.status_code if response.status_code >= 400 else 401
            raise GitHubError(status, body.get("error_description") or body.get("error") or "no token")
        return Grant(
            body["access_token"],
            body.get("scope") or "",
            seconds(body.get("expires_in")),
            body.get("refresh_token") or None,
            seconds(body.get("refresh_token_expires_in")),
        )

    def exchange(self, client_id: str, client_secret: str, code: str, redirect_uri: str) -> Grant:
        """The token a code from the authorization page is worth, with its scopes and, where it expires, its refresh."""
        return self._grant(
            {"client_id": client_id, "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri}
        )

    def refresh(self, client_id: str, client_secret: str, refresh_token: str) -> Grant:
        """A new user token and refresh token for a refresh token, which GitHub retires with the old token.

        Raises:
            GitHubError: 401 where GitHub refused the refresh token: expired, revoked, or already used.
        """
        return self._grant(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )

    def user(self, token: str) -> dict[str, Any]:
        """The account a token is for: `login`, `id`, `name`, and `avatar_url` among the rest."""
        return self._call("GET", f"{API_URL}/user", token)

    def installations(self, token: str, limit: int = 1000) -> list[dict[str, Any]]:
        """The GitHub App's installations the token's user can reach a repository of."""
        return self._pages("/user/installations", token, "installations", limit)

    def installation_repositories(self, token: str, installation_id: int, limit: int) -> list[dict[str, Any]]:
        """The repositories of one installation the token's user can reach, each with the user's `permissions`."""
        return self._pages(f"/user/installations/{int(installation_id)}/repositories", token, "repositories", limit)

    def registry_pull(self, login: str, token: str, scope: str = EPIC_PULL) -> bool:
        """Whether the container registry grants the account a pull of an image: its token service's own answer.

        The service answers a pull it grants with 200 and a token, and one it does not with 401 or
        403, whether the account may not pull that image or the token is not good at all; the
        caller asks GitHub which, where it matters.

        Raises:
            GitHubError: The registry answered with anything else.
        """
        response = self.http.get(
            REGISTRY_TOKEN_URL,
            params={"scope": scope, "service": REGISTRY_SERVICE},
            auth=(login, token),
            headers={"Accept": "application/json"},
        )
        if response.status_code == 200:
            return True
        if response.status_code in (401, 403):
            return False
        raise GitHubError(response.status_code, f"ghcr.io answered {response.status_code}")

    def repo(self, token: str, full_name: str) -> dict[str, Any]:
        """One repository, with the account's `permissions` on it."""
        return self._call("GET", f"{API_URL}/repos/{full_name}", token)

    def head(self, token: str, full_name: str, branch: str) -> str | None:
        """The commit a branch points at, or nothing where the repository has no branch of that name."""
        try:
            return self._call("GET", f"{API_URL}/repos/{full_name}/git/ref/heads/{quote(branch)}", token)["object"]["sha"]
        except GitHubError as error:
            if error.status == 404:
                return None
            raise

    def branches_under(self, token: str, full_name: str, prefix: str) -> list[str]:
        """The names of the repository's branches that start with a prefix, such as `moody/`.

        GitHub is asked without the prefix's closing slash, which not every proxy in front of it
        passes, and the names are held to the whole prefix here.
        """
        asked = quote(prefix.rstrip("/"))
        refs = self._call("GET", f"{API_URL}/repos/{full_name}/git/matching-refs/heads/{asked}", token)
        names = [ref["ref"][len("refs/heads/") :] for ref in refs]
        return [name for name in names if name.startswith(prefix)]

    def create_branch(self, token: str, full_name: str, branch: str, sha: str) -> None:
        """Make a branch at a commit; GitHub refuses one whose name is taken."""
        self._call("POST", f"{API_URL}/repos/{full_name}/git/refs", token, json={"ref": f"refs/heads/{branch}", "sha": sha})

    def tree(self, token: str, full_name: str, sha: str, recursive: bool) -> dict[str, Any]:
        """One listing of the Git Trees API: a tree's `tree` entries, under it or all below it, and whether it was `truncated`."""
        return self._call(
            "GET", f"{API_URL}/repos/{full_name}/git/trees/{sha}", token, params={"recursive": "1"} if recursive else None
        )

    def files(self, token: str, full_name: str, sha: str, calls: int = TREE_CALLS) -> tuple[list[dict[str, Any]], bool]:
        """Every entry below a commit or tree, with its path from the top, and whether the listing is whole.

        A recursive listing holds the whole tree unless GitHub truncated it,
        which it does past 100,000 entries or 7 MB. A truncated tree is listed
        again without recursion, and each of its subtrees is listed the same way
        as the whole was, so a large repository costs one call for each tree
        too large to list at once and one for each subtree below those. The
        walk stops after `calls` calls, which keeps one question about a vast
        repository from spending the account's hourly allowance; the listing
        is then not whole.
        """
        entries: list[dict[str, Any]] = []
        pending = [("", sha)]
        whole = True
        made = 0
        while pending:
            if made >= calls:
                return entries, False
            prefix, tree_sha = pending.pop()
            made += 1
            listing = self.tree(token, full_name, tree_sha, recursive=True)
            if listing.get("truncated"):
                if made >= calls:
                    return entries, False
                made += 1
                listing = self.tree(token, full_name, tree_sha, recursive=False)
                whole = whole and not listing.get("truncated")
                pending.extend((f"{prefix}{entry['path']}/", entry["sha"]) for entry in listing["tree"] if entry["type"] == "tree")
            entries.extend({**entry, "path": f"{prefix}{entry['path']}"} for entry in listing["tree"])
        return entries, whole

    def read(self, token: str, full_name: str, path: str, ref: str | None = None) -> dict[str, Any]:
        """A file's text and its blob SHA, or a directory's listing as `entries`, on the default branch or at `ref`."""
        body = self._call(
            "GET", f"{API_URL}/repos/{full_name}/contents/{quote(path)}", token, params={"ref": ref} if ref else None
        )
        if isinstance(body, list):
            return {"entries": [f"{entry['name']}{'/' if entry['type'] == 'dir' else ''}" for entry in body]}
        if body.get("encoding") != "base64":
            raise GitHubError(413, "That file is too large to read through the contents API.")
        return {"text": base64.b64decode(body["content"]).decode("utf-8", errors="replace"), "sha": body["sha"]}

    def save(self, token: str, full_name: str, path: str, content: str, message: str, branch: str) -> dict[str, Any]:
        """Write a file in one commit on a branch, creating it or replacing what is there; returns the commit."""
        try:
            sha = self.read(token, full_name, path, ref=branch).get("sha")
        except GitHubError as error:
            if error.status != 404:
                raise
            sha = None
        body: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        return self._call("PUT", f"{API_URL}/repos/{full_name}/contents/{quote(path)}", token, json=body)["commit"]
