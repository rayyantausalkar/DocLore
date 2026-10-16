import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional


_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$")


def _allow_non_github() -> bool:
    return os.getenv("DOCLORE_ALLOW_LOCAL_REPOS", "").lower() in {"1", "true", "yes"}


@dataclass
class GitHubRepoInfo:
    clone_url: str
    owner: str
    repo_name: str
    branch: Optional[str] = None
    subpath: Optional[str] = None


class GitHubRepoManager:
    """Deep module for ingesting repositories from GitHub URLs.
    
    Handles URL normalization, shallow git cloning, incremental pulling,
    and Python file extraction with commit revision tracking.
    """

    def parse_github_url(self, raw_url: str) -> GitHubRepoInfo:
        """Parses various GitHub URL formats into structured repo coordinates.
        
        Supports:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - https://github.com/owner/repo/tree/main
        - https://github.com/owner/repo/tree/v1.0.0/src/services
        - git@github.com:owner/repo.git
        """
        clean_url = raw_url.strip()

        # Handle SSH style
        ssh_match = re.match(r"^git@github\.com:([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?$", clean_url)
        if ssh_match:
            owner, repo = ssh_match.group(1), ssh_match.group(2)
            return GitHubRepoInfo(
                clone_url=f"https://github.com/{owner}/{repo}.git",
                owner=owner,
                repo_name=repo,
            )

        # Handle HTTPS URLs
        https_tree_match = re.match(
            r"^https?://github\.com/([\w\-\.]+)/([\w\-\.]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?/?$",
            clean_url,
        )
        if https_tree_match:
            owner = https_tree_match.group(1)
            repo = https_tree_match.group(2)
            branch = https_tree_match.group(3)
            subpath = https_tree_match.group(4)
            return GitHubRepoInfo(
                clone_url=f"https://github.com/{owner}/{repo}.git",
                owner=owner,
                repo_name=repo,
                branch=branch,
                subpath=subpath,
            )

        # Fallback standard URL or local directory/file path
        if clean_url.startswith("http://") or clean_url.startswith("https://"):
            clone_url = clean_url if clean_url.endswith(".git") else f"{clean_url}.git"
        else:
            clone_url = clean_url

        return GitHubRepoInfo(
            clone_url=clone_url,
            owner="unknown",
            repo_name=os.path.basename(clean_url.rstrip("/\\")).replace(".git", "") or "repo",
        )

    def sync_and_extract_files(
        self,
        github_url: str,
        target_dir: str,
        branch: Optional[str] = None,
        subpath: Optional[str] = None,
        file_extensions: Optional[tuple[str, ...]] = None,
    ) -> tuple[str, list[tuple[str, str]]]:
        """Clones or updates a GitHub repo and extracts matching source files across all supported languages.
        
        Returns:
            A tuple of (commit_revision, [(relative_path, file_content), ...])
        """
        from doclore_api.ingestion.repository import (
            DEFAULT_IGNORE_DIRS,
            DEFAULT_IGNORE_FILES,
            DEFAULT_REPOSITORY_EXTENSIONS,
            EXACT_FILENAME_MATCHES,
            MAX_FILE_SIZE_BYTES,
        )

        parsed = self.parse_github_url(github_url)
        effective_branch = branch or parsed.branch
        effective_subpath = subpath or parsed.subpath
        effective_exts = tuple(file_extensions) if file_extensions else DEFAULT_REPOSITORY_EXTENSIONS
        clone_url = parsed.clone_url

        if clone_url.startswith("-"):
            raise ValueError("Invalid repository URL.")
        if parsed.owner == "unknown" and not _allow_non_github():
            raise ValueError(
                "Only GitHub repository URLs are supported (e.g. https://github.com/owner/repo)."
            )
        if effective_branch and not _SAFE_REF.match(effective_branch):
            raise ValueError(f"Invalid branch name: '{effective_branch}'.")

        os.makedirs(os.path.dirname(target_dir), exist_ok=True)

        try:
            if os.path.isdir(os.path.join(target_dir, ".git")):
                # Pull latest updates
                subprocess.run(
                    ["git", "-C", target_dir, "pull"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            else:
                cmd = ["git", "clone", "--depth", "1"]
                if effective_branch:
                    cmd.extend(["--branch", effective_branch])
                cmd.extend(["--", clone_url, target_dir])
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            # Extract HEAD commit hash for revision provenance
            rev_res = subprocess.run(
                ["git", "-C", target_dir, "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commit_hash = rev_res.stdout.strip()[:16]

        except subprocess.CalledProcessError as exc:
            err_msg = exc.stderr.strip() if exc.stderr else exc.stdout.strip()
            raise ValueError(f"Failed to clone/pull GitHub repository '{github_url}': {err_msg}") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"GitHub git clone operation timed out for repository '{github_url}'.") from exc

        # Scan for matching source files
        repo_root = os.path.realpath(target_dir)
        search_root = (
            os.path.realpath(os.path.join(target_dir, effective_subpath))
            if effective_subpath
            else repo_root
        )
        if search_root != repo_root and not search_root.startswith(repo_root + os.sep):
            raise ValueError("Subpath must stay inside the repository.")
        if not os.path.isdir(search_root):
            raise FileNotFoundError(f"Specified subpath '{effective_subpath}' not found in cloned GitHub repository.")

        payloads: list[tuple[str, str]] = []

        for root, dirs, files in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORE_DIRS]
            for file_name in files:
                if file_name in DEFAULT_IGNORE_FILES:
                    continue
                if file_name.endswith((".min.js", ".min.css", ".map", ".bundle.js", ".pyc", ".pyo", ".pyd")):
                    continue

                is_supported = (
                    any(file_name.endswith(ext) for ext in effective_exts)
                    or file_name in EXACT_FILENAME_MATCHES
                )
                if not is_supported:
                    continue

                full_path = os.path.join(root, file_name)
                real_full = os.path.realpath(full_path)
                if not real_full.startswith(repo_root + os.sep):
                    continue

                try:
                    # Guard against huge binary or data dump files
                    if os.path.getsize(full_path) > MAX_FILE_SIZE_BYTES:
                        continue

                    with open(full_path, "rb") as f:
                        header = f.read(8000)
                        if b"\x00" in header:
                            continue  # Skip binary file

                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        rel_path = os.path.relpath(real_full, repo_root).replace("\\", "/")
                        payloads.append((rel_path, f.read()))
                except Exception:
                    continue

        if not payloads:
            raise ValueError(
                f"No matching files found in GitHub repository '{github_url}'."
            )

        return commit_hash, payloads
