#!/usr/bin/env python3
"""Import public X posts/Articles as Markdown, EPUB, and optionally Send-to-Kindle.

Runs on the desktop. Does not alter the KOReader/SimpleUI installation.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

API = "https://xtracticle.com/api/markdown/"
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https://[^\s)]+)(?:\s+[\"'][^)]+[\"'])?\)")
HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
TITLE_RE = re.compile(r"^title:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
IMAGE_HOSTS = {"pbs.twimg.com", "abs.twimg.com", "ton.twimg.com", "video.twimg.com"}
MAX_MARKDOWN = 4 * 1024 * 1024
MAX_IMAGE = 12 * 1024 * 1024
MAX_TOTAL_IMAGES = 48 * 1024 * 1024
MAX_IMAGES = 60


class ImportError_(RuntimeError):
    pass


def post_id_from_url(value: str) -> str:
    parts = urllib.parse.urlsplit(value.strip())
    if parts.scheme != "https" or parts.username or parts.password or parts.port:
        raise ImportError_("请提供 https://x.com/用户名/status/数字ID 格式的公开帖子链接")
    if parts.hostname not in X_HOSTS:
        raise ImportError_("仅支持 x.com 或 twitter.com 的帖子链接")
    matched = re.fullmatch(r"/(?:[^/]+/status|i/web/status)/(\d+)/?", parts.path)
    if not matched:
        raise ImportError_("当前需要 X 帖子的 status 链接；/i/article/ 链接请换成对应的帖子 URL")
    return matched.group(1)


def title_from_markdown(markdown: str, fallback: str) -> str:
    match = TITLE_RE.search(markdown)
    if match:
        title = match.group(1).strip().strip("'\"")
        if title:
            return title[:160]
    match = HEADING_RE.search(markdown)
    return match.group(1).strip()[:160] if match else fallback


def fetch_markdown(url: str, provider: str = "xtracticle") -> tuple[str, str]:
    post_id = post_id_from_url(url)
    if provider == "x2md":
        if shutil.which("x2md") is None:
            raise ImportError_("本地缺少 x2md。先安装：pipx install git+https://github.com/yshmarov/x2md")
        try:
            result = subprocess.run(
                ["x2md", url, "--no-replies"], capture_output=True, text=True,
                check=True, timeout=80, encoding="utf-8",
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ImportError_(f"x2md 抓取失败：{exc}") from exc
        markdown = result.stdout
    elif provider == "xtracticle":
        query = urllib.parse.urlencode({"format": "markdown", "thread": "1", "front_matter": "1"})
        request = urllib.request.Request(
            f"{API}{post_id}?{query}",
            headers={"User-Agent": "x-to-kindle/0.1", "Accept": "text/markdown, text/plain"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                if response.status != 200:
                    raise ImportError_(f"抓取接口返回 HTTP {response.status}")
                data = response.read(MAX_MARKDOWN + 1)
                content_type = response.headers.get("Content-Type", "")
        except (OSError, urllib.error.URLError) as exc:
            raise ImportError_(f"Xtracticle 抓取失败：{exc}") from exc
        if len(data) > MAX_MARKDOWN:
            raise ImportError_("正文超出 4MB 安全上限")
        if "json" in content_type.lower():
            raise ImportError_("抓取接口返回 JSON，可能是错误响应")
        markdown = data.decode("utf-8-sig", errors="replace")
    else:
        raise ImportError_(f"未知抓取提供方：{provider}")
    if len(markdown.strip()) < 40:
        raise ImportError_("抓取结果异常短，拒绝生成可能缺失正文的电子书")
    return post_id, markdown


def save_markdown(url: str, output_dir: Path, provider: str) -> Path:
    post_id, markdown = fetch_markdown(url, provider)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"x-{post_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def _safe_image_url(url: str) -> str:
    parts = urllib.parse.urlsplit(html.unescape(url))
    if parts.scheme != "https" or parts.hostname not in IMAGE_HOSTS:
        raise ImportError_(f"图片域名不在允许列表内：{parts.hostname}")
    if parts.username or parts.password or parts.port:
        raise ImportError_("图片地址包含不允许的认证或端口参数")
    return parts.geturl()


class _ImageRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        _safe_image_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def _image_ext(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    raise ImportError_("图片并非可直接用于 Kindle EPUB 的 JPEG、PNG 或 GIF")


def embed_images(markdown: str, media_dir: Path, allow_missing: bool = False) -> tuple[str, int]:
    matches = list(IMAGE_RE.finditer(markdown))
    if len(matches) > MAX_IMAGES:
        raise ImportError_(f"文章有 {len(matches)} 张图片，超过单篇 {MAX_IMAGES} 张的上限")
    media_dir.mkdir(exist_ok=True)
    opener = urllib.request.build_opener(_ImageRedirect())
    cache: dict[str, str] = {}
    total = 0
    copied = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal total, copied
        alt, original = match.group(1), match.group(2)
        try:
            url = _safe_image_url(original)
            if url in cache:
                return f"![{alt}]({cache[url]})"
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(request, timeout=20) as response:
                length = int(response.headers.get("Content-Length", "0"))
                if length > MAX_IMAGE:
                    raise ImportError_("图片超过单张大小上限 12MB")
                payload = response.read(MAX_IMAGE + 1)
            if len(payload) > MAX_IMAGE or total + len(payload) > MAX_TOTAL_IMAGES:
                raise ImportError_("图片总大小超出安全上限 48MB")
            extension = _image_ext(payload)
            filename = f"image-{len(cache) + 1:03d}{extension}"
            (media_dir / filename).write_bytes(payload)
            relative = f"media/{filename}"
            cache[url] = relative
            total += len(payload)
            copied += 1
            return f"![{alt}]({relative})"
        except (OSError, ValueError, urllib.error.URLError, ImportError_) as exc:
            if not allow_missing:
                raise ImportError_(f"图片下载失败（{original}）：{exc}") from exc
            return f"[{alt or '原图'}]({original})"

    return IMAGE_RE.sub(replace, markdown), copied


def build_epub(markdown_path: Path, output: Path | None = None, allow_missing: bool = False) -> Path:
    if not markdown_path.is_file():
        raise ImportError_(f"找不到 Markdown 文件：{markdown_path}")
    if shutil.which("pandoc") is None:
        raise ImportError_("缺少 Pandoc，请先安装并确保 pandoc 命令可用")
    original = markdown_path.read_text(encoding="utf-8")
    if len(original.strip()) < 40:
        raise ImportError_("Markdown 正文太短，已停止转换")
    title = title_from_markdown(original, markdown_path.stem)
    target = (output or markdown_path.with_suffix(".epub")).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_name(target.stem + ".building.epub")
    if temp_target.exists():
        raise ImportError_(f"存在尚未处理的临时文件：{temp_target}")
    with tempfile.TemporaryDirectory(prefix="x-to-kindle-") as directory:
        work = Path(directory)
        localized, image_count = embed_images(original, work / "media", allow_missing)
        source = work / "article.md"
        source.write_text(localized, encoding="utf-8")
        command = [
            "pandoc", "--from=markdown+yaml_metadata_block", "--to=epub3",
            "--standalone", "--metadata", f"title={title}",
            "--output", str(temp_target), str(source),
        ]
        try:
            subprocess.run(command, cwd=work, check=True, capture_output=True, text=True, timeout=120)
            with zipfile.ZipFile(temp_target) as archive:
                names = archive.namelist()
                if archive.testzip() or "META-INF/container.xml" not in names:
                    raise ImportError_("EPUB 结构验证失败")
                if image_count and not any(
                    name.lower().endswith((".jpg", ".jpeg", ".png", ".gif")) for name in names
                ):
                    raise ImportError_("EPUB 缺失已下载图片，拒绝提交不完整文档")
            temp_target.replace(target)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, zipfile.BadZipFile) as exc:
            raise ImportError_(f"EPUB 生成失败：{exc}") from exc
        finally:
            temp_target.unlink(missing_ok=True)
    return target


def send_to_kindle(epub: Path, title: str | None = None) -> None:
    if not epub.is_file() or epub.suffix.lower() != ".epub":
        raise ImportError_("只允许发送已经生成的 EPUB 文件")
    if shutil.which("kindlemcp-send") is None:
        raise ImportError_("缺少 kindlemcp-send，请先安装：pipx install kindlemcp")
    try:
        subprocess.run(
            ["kindlemcp-send", "--title", title or epub.stem, str(epub.resolve())],
            check=True, capture_output=True, text=True, timeout=90,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ImportError_(f"发送失败，EPUB 已保存在本地：{exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="X Article / Thread → Markdown → EPUB → Kindle")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="抓取 X 原文")
    fetch.add_argument("url")
    fetch.add_argument("--out-dir", type=Path, default=Path("articles"))
    fetch.add_argument("--provider", choices=("xtracticle", "x2md"), default="xtracticle")
    epub = sub.add_parser("epub", help="将 Markdown 打包为 EPUB")
    epub.add_argument("markdown", type=Path)
    epub.add_argument("--output", type=Path)
    epub.add_argument("--allow-missing-images", action="store_true")
    send = sub.add_parser("send", help="明确发送已经生成的 EPUB")
    send.add_argument("epub", type=Path)
    send.add_argument("--title")
    all_cmd = sub.add_parser("all", help="抓取、打包，可选发送")
    all_cmd.add_argument("url")
    all_cmd.add_argument("--out-dir", type=Path, default=Path("articles"))
    all_cmd.add_argument("--provider", choices=("xtracticle", "x2md"), default="xtracticle")
    all_cmd.add_argument("--allow-missing-images", action="store_true")
    all_cmd.add_argument("--send", action="store_true", help="明确允许发送至 Kindle 邮箱")
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            print(save_markdown(args.url, args.out_dir, args.provider))
        elif args.command == "epub":
            print(build_epub(args.markdown, args.output, args.allow_missing_images))
        elif args.command == "send":
            send_to_kindle(args.epub, args.title)
            print("已向发送工具提交 EPUB，请在 Kindle 端检查是否收到")
        elif args.command == "all":
            markdown = save_markdown(args.url, args.out_dir, args.provider)
            output = build_epub(markdown, allow_missing=args.allow_missing_images)
            print(output)
            if args.send:
                send_to_kindle(output, title_from_markdown(markdown.read_text(encoding="utf-8"), output.stem))
                print("已向发送工具提交 EPUB，请在 Kindle 端检查是否收到")
    except ImportError_ as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
