# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""GitHub for Lathe: the OAuth App a user connects their account through, and the API calls made with it.

A user connects once. The control plane sends them to GitHub's authorization
page with a `state` it signed, GitHub sends them back to the callback with a
code, and the control plane trades the code for a token with its client secret.
The callback carries no credential of the user's own, being a redirect from
GitHub, so the state is what says whom the token is for: it names the user,
the page to return to, and an expiry, under an HMAC keyed by `LATHE_SECRET_KEY`
(`sign_state`, `read_state`). A state nobody signed, or one past its expiry, is
refused before anything is exchanged, and the page it names is never visited,
which with the check that it lies under the site's own address
(`Sessions.github_connect`) keeps the callback from redirecting anywhere else.

The token is stored only encrypted, with Fernet under a key derived from the
same secret (`seal`, `unseal`), and leaves the control plane only in requests
to GitHub, and as the user's own credential for pulling their copy of an app
from GitHub's container registry, which the launcher keeps as that user's own
Modal Secret (`launcher.py`). Each key derived
from the secret is for one purpose, so a signed state can never be read as a
sealed token or the reverse.

The app asks for `repo`, for the project's repository, and `read:packages`,
for that pull. Whether a user's account is linked to Epic is read from what
their token can see (`GitHub.epic_access`): Epic gives a linked account the
private `EpicGames/UnrealEngine` repository, through its organization, and the
engine's container images on `ghcr.io/epicgames/unreal-engine`. GitHub hides
what a token cannot see behind a 404, so a 404 is "not linked", never an error.

A write names its branch (`GitHub.save`), on the read of what is there and on
the commit alike: the contents API commits to the repository's default branch
when none is named, and the default branch of a team's repository is the one
place Lathe's agent must never write (`agent.py`, `tool_github_save`).

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
# Space-delimited, as the authorization page takes them; GitHub lists what it granted with commas
SCOPE = "repo read:packages"
PACKAGE_SCOPES = frozenset({"read:packages", "write:packages"})
STATE_SECONDS = 600
# What an account linked to Epic can see: the engine's source and its container images
EPIC_REPO = "EpicGames/UnrealEngine"
EPIC_PACKAGE = "/orgs/EpicGames/packages/container/unreal-engine"
# Calls one listing of a repository's files may make, at most: a walk of a vast tree stops there
TREE_CALLS = 200


class Grant(NamedTuple):
    """What GitHub granted for an authorization: the token, and its scopes as GitHub lists them."""

    token: str
    scope: str


def reads_packages(scope: str) -> bool:
    """Whether a grant's scopes let its token pull from GitHub's container registry."""
    return bool(PACKAGE_SCOPES & {part.strip() for part in scope.split(",")})


class GitHubError(Exception):
    """A call GitHub refused, with its status and what it said."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _key(secret: str, purpose: str) -> bytes:
    """A key for one purpose, derived from the deployment's secret."""
    return hmac.new(secret.encode(), f"lathe {purpose}".encode(), hashlib.sha256).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_state(secret: str, user_id: str, return_to: str, now: float | None = None) -> str:
    """The `state` of an authorization: the user and the page to return to, expiring, under an HMAC."""
    payload = {
        "u": user_id,
        "r": return_to,
        "e": int((now if now is not None else time.time()) + STATE_SECONDS),
        "n": secrets.token_urlsafe(8),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    mac = hmac.new(_key(secret, "github state"), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(mac)}"


def read_state(secret: str, state: str, now: float | None = None) -> dict[str, Any] | None:
    """What a `state` says, or nothing where it was not signed with the secret, is malformed, or has expired."""
    body, _, mac = state.partition(".")
    if not body or not mac or not secret:
        return None
    expected = hmac.new(_key(secret, "github state"), body.encode(), hashlib.sha256).digest()
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


class GitHub:
    """GitHub's OAuth endpoints and REST API, as far as Lathe uses them.

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

    @staticmethod
    def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
        """The page that asks the user to let Lathe reach their repositories."""
        query = {"client_id": client_id, "redirect_uri": redirect_uri, "scope": SCOPE, "state": state}
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    def exchange(self, client_id: str, client_secret: str, code: str, redirect_uri: str) -> Grant:
        """The token a code from the authorization page is worth, with the scopes it carries."""
        response = self.http.post(
            TOKEN_URL,
            headers={"Accept": "application/json"},
            data={"client_id": client_id, "client_secret": client_secret, "code": code, "redirect_uri": redirect_uri},
        )
        body = response.json() if response.content else {}
        if response.status_code >= 400 or not body.get("access_token"):
            raise GitHubError(response.status_code, body.get("error_description") or body.get("error") or "no token")
        return Grant(body["access_token"], body.get("scope") or "")

    def user(self, token: str) -> dict[str, Any]:
        """The account a token is for: `login` and `avatar_url` among the rest."""
        return self._call("GET", f"{API_URL}/user", token)

    def epic_access(self, token: str) -> bool:
        """Whether the token's account is linked to Epic: it sees Unreal Engine's repository and its images.

        The images are read with `read:packages`, so the token has to have been granted it
        (`reads_packages`).

        Raises:
            GitHubError: GitHub refused for another reason than not showing the account either one.
        """
        for path in (f"/repos/{EPIC_REPO}", EPIC_PACKAGE):
            try:
                self._call("GET", f"{API_URL}{path}", token)
            except GitHubError as error:
                if error.status == 404:
                    return False
                raise
        return True

    def repos(self, token: str) -> list[dict[str, Any]]:
        """The repositories the account can push to, most recently updated first."""
        return self._call(
            "GET", f"{API_URL}/user/repos", token, params={"sort": "updated", "per_page": 100, "affiliation": "owner,collaborator,organization_member"}
        )

    def repo(self, token: str, full_name: str) -> dict[str, Any]:
        """One repository, with the account's `permissions` on it."""
        return self._call("GET", f"{API_URL}/repos/{full_name}", token)

    def create_repo(self, token: str, name: str, private: bool) -> dict[str, Any]:
        """A new repository of the account's own, with a first commit so files can be saved into it at once."""
        return self._call(
            "POST", f"{API_URL}/user/repos", token, json={"name": name, "private": private, "auto_init": True}
        )

    def head(self, token: str, full_name: str, branch: str) -> str | None:
        """The commit a branch points at, or nothing where the repository has no branch of that name."""
        try:
            return self._call("GET", f"{API_URL}/repos/{full_name}/git/ref/heads/{quote(branch)}", token)["object"]["sha"]
        except GitHubError as error:
            if error.status == 404:
                return None
            raise

    def branches_under(self, token: str, full_name: str, prefix: str) -> list[str]:
        """The names of the repository's branches that start with a prefix, such as `lathe/`.

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
