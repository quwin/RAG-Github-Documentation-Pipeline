from pathlib import Path
import json
import subprocess
from dataclasses import asdict
from urllib.parse import urlparse
from langchain_core.documents import Document

# Example Usage:

# repo_path = "https://github.com/fastapi/fastapi"
# head_branch = get_head_branch(repo_path)
# docs = load_documents_from_repo(repo_path ,data_dir="data", branch=head_branch)
# print(f"Loaded {len(docs)} documentation files")
# for doc in docs[:5]:
#     print(doc.source_path, doc.metadata["char_count"])

DOC_EXTENSIONS = {
    ".md",
    ".mdx",
    ".rst",
    ".txt",
    ".adoc",
    ".ipynb",
}

DOC_FILENAMES = {
    "readme",
    "readme.md",
    "changelog",
    "changelog.md",
    "contributing",
    "contributing.md",
    "license",
    "license.md",
}

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

EXCLUDE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".mp4",
    ".mov",
    ".exe",
    ".dll",
    ".so",
}


def validate_github_url(repo_url: str) -> None:
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"https"}:
        raise ValueError("Only HTTPS GitHub URLs are allowed.")
    if parsed.netloc != "github.com":
        raise ValueError("Only github.com repositories are allowed.")
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Expected a GitHub repo URL like https://github.com/owner/repo.")


def get_repo_name(repo_url: str) -> str:
    parts = urlparse(repo_url).path.strip("/").split("/")
    owner, repo = parts[0], parts[1].replace(".git", "")
    return f"{owner}__{repo}"

def get_head_branch(repo_url: str) -> str:
    result = subprocess.run(
        ["git", "ls-remote", "--symref", repo_url, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    for line in result.stdout.splitlines():
        if line.startswith("ref:"):
            # Example:
            # ref: refs/heads/main	HEAD
            ref = line.split()[1]
            return ref.removeprefix("refs/heads/")
    raise RuntimeError(f"Could not determine default branch for {repo_url}")

def run_git(args: list[str], cwd: Path | None = None, timeout=120) -> None:
    subprocess.run(args,cwd=cwd,check=True,timeout=timeout)

def clone_repo(repo_url: str, clone_root: Path, branch: str = "master") -> Path:
    validate_github_url(repo_url)
    repo_name = get_repo_name(repo_url)
    repo_path = clone_root / repo_name
    clone_root.mkdir(parents=True, exist_ok=True)
    if not repo_path.exists():
        run_git(["git", "clone", "--depth", "1", "--single-branch", "--branch", branch, repo_url, str(repo_path)])
        return repo_path
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        raise ValueError(f"{repo_path} already exists but is not a Git repository. Delete it manually or choose a different clone_root.")
    run_git(["git", "remote", "set-url", "origin", repo_url], cwd=repo_path)
    run_git(["git", "fetch", "--depth", "1", "origin", branch], cwd=repo_path)
    run_git(["git", "reset", "--hard", f"origin/{branch}"], cwd=repo_path)
    run_git(["git", "clean", "-fdx"], cwd=repo_path)
    return repo_path


def is_documentation_file(path: Path, repo_root: Path) -> bool:
    relative_parts = path.relative_to(repo_root).parts

    if any(part in EXCLUDE_DIRS for part in relative_parts):
        return False

    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return False

    filename = path.name.lower()

    if filename in DOC_FILENAMES:
        return True

    if path.suffix.lower() in DOC_EXTENSIONS:
        return True

    if "docs" in relative_parts or "documentation" in relative_parts:
        return path.suffix.lower() in DOC_EXTENSIONS

    return False


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def extract_markdown_headings(text: str) -> list[str]:
    headings = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                headings.append(heading)

    return headings


def load_documents_from_repo(repo_url: str, data_dir: str = "data", branch: str = "master") -> list[Document]:
    data_path = Path(data_dir)
    clone_root = data_path / "raw" / "repos"
    processed_root = data_path / "processed"

    repo_path = clone_repo(repo_url, clone_root, branch)
    repo_name = repo_path.name

    documents: list[Document] = []

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue

        if not is_documentation_file(path, repo_path):
            continue

        content = read_text_file(path)
        relative_path = str(path.relative_to(repo_path))

        metadata = {
            "repo_url": repo_url,
            "repo_name": repo_name,
            "source_path": relative_path,
            "file_type": path.suffix.lower(),
            "section_headings": extract_markdown_headings(content),
            "char_count": len(content),
        }
        documents.append(Document(page_content=content, metadata=metadata))

    processed_root.mkdir(parents=True, exist_ok=True)

    output_path = processed_root / f"{repo_name}_documents.jsonl"

    with output_path.open("w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")

    return documents