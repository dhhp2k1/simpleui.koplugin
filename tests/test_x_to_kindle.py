"""Offline regression tests for the desktop X-to-Kindle tool.

No real network requests, no actual Pandoc execution, and no email.
"""
import contextlib
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "x_to_kindle.py"
spec = importlib.util.spec_from_file_location("x_to_kindle", SOURCE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

TEXT = "# A meaningful X article\n\n" + ("This is the original article text. " * 10)


class Response(io.BytesIO):
    status = 200
    def __init__(self, data, headers=None):
        super().__init__(data)
        self.headers = headers or {"Content-Type": "text/markdown"}


class XToKindleTests(unittest.TestCase):
    def test_valid_status_links_and_query(self):
        self.assertEqual(tool.post_id_from_url("https://x.com/someone/status/123?ref=share"), "123")
        self.assertEqual(tool.post_id_from_url("https://twitter.com/a/status/987"), "987")
        self.assertEqual(tool.post_id_from_url("https://x.com/i/web/status/1234"), "1234")

    def test_rejects_unsafe_or_unsupported_links(self):
        urls = [
            "http://x.com/a/status/1",
            "https://evil.test/a/status/1",
            "https://x.com.evil.test/a/status/1",
            "https://x.com:444/a/status/1",
            "https://user:secret@x.com/a/status/1",
            "https://x.com/i/article/123",
            "file:///etc/passwd",
            "https://x.com/a/status/abc",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(tool.ImportError_):
                tool.post_id_from_url(url)

    def test_xtracticle_api_markdown_and_thread(self):
        urls = []
        def fake_urlopen(request, timeout):
            urls.append(request.full_url)
            return Response(TEXT.encode("utf-8"))
        with mock.patch.object(tool.urllib.request, "urlopen", side_effect=fake_urlopen):
            post_id, markdown = tool.fetch_markdown("https://x.com/u/status/123")
        self.assertEqual(post_id, "123")
        self.assertEqual(markdown, TEXT)
        self.assertIn("front_matter=1", urls[0])
        self.assertIn("thread=1", urls[0])
        self.assertTrue(urls[0].startswith(tool.API + "123?"))

    def test_empty_and_json_responses_fail_closed(self):
        for data, headers in [
            (b"bad", {"Content-Type": "text/markdown"}),
            (b'{"error":"' + b"x" * 100 + b'"}', {"Content-Type": "application/json"}),
        ]:
            with mock.patch.object(tool.urllib.request, "urlopen", return_value=Response(data, headers)):
                with self.assertRaises(tool.ImportError_):
                    tool.fetch_markdown("https://x.com/u/status/123")

    def test_x2md_is_explicit_option(self):
        fake = mock.Mock(returncode=0, stdout=TEXT)
        with mock.patch.object(tool.shutil, "which", return_value="/usr/bin/x2md"), \
             mock.patch.object(tool.subprocess, "run", return_value=fake) as runner:
            _, body = tool.fetch_markdown("https://x.com/u/status/55", provider="x2md")
        self.assertEqual(body, TEXT)
        self.assertIn("--no-replies", runner.call_args.args[0])

    def test_title_uses_yaml_then_heading(self):
        self.assertEqual(tool.title_from_markdown('title: "Found title"\n# Another title', "fallback"), "Found title")
        self.assertEqual(tool.title_from_markdown(TEXT, "fallback"), "A meaningful X article")

    def test_image_host_filter(self):
        self.assertEqual(tool._safe_image_url("https://pbs.twimg.com/media/a.jpg"), "https://pbs.twimg.com/media/a.jpg")
        for url in ["https://127.0.0.1/img", "https://pbs.twimg.com.evil.test/a", "http://pbs.twimg.com/a"]:
            with self.assertRaises(tool.ImportError_):
                tool._safe_image_url(url)

    def test_download_images_and_keep_order(self):
        photo = bytes([0xFF, 0xD8, 0xFF]) + b"x" * 128
        class Opener:
            def open(self, request, timeout=None):
                return Response(photo, {"Content-Length": str(len(photo))})
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(tool.urllib.request, "build_opener", return_value=Opener()):
                md, count = tool.embed_images(
                    "before ![cover](https://pbs.twimg.com/media/a.jpg) after",
                    Path(tmp) / "media"
                )
            self.assertEqual(count, 1)
            self.assertIn("media/image-001.jpg", md)
            self.assertTrue((Path(tmp) / "media" / "image-001.jpg").is_file())

    def test_image_download_failure_stops_conversion(self):
        class Opener:
            def open(self, request, timeout=None):
                raise OSError("offline")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(tool.urllib.request, "build_opener", return_value=Opener()):
                with self.assertRaises(tool.ImportError_):
                    tool.embed_images("![x](https://pbs.twimg.com/media/a.jpg)", Path(tmp) / "media")
                result, count = tool.embed_images(
                    "![x](https://pbs.twimg.com/media/a.jpg)", Path(tmp) / "media", True
                )
        self.assertEqual(count, 0)
        self.assertIn("https://pbs.twimg.com/media/a.jpg", result)

    def test_epub_build_and_archive_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "article.md"
            md_path.write_text(TEXT, encoding="utf-8")
            def fake_pandoc(argv, **kwargs):
                target = Path(argv[argv.index("--output") + 1])
                with zipfile.ZipFile(target, "w") as z:
                    z.writestr("mimetype", "application/epub+zip")
                    z.writestr("META-INF/container.xml", "<container/>")
            with mock.patch.object(tool.shutil, "which", return_value="/bin/pandoc"), \
                 mock.patch.object(tool.subprocess, "run", side_effect=fake_pandoc):
                out = tool.build_epub(md_path)
            self.assertEqual(out.suffix, ".epub")
            with zipfile.ZipFile(out) as z:
                self.assertEqual(z.read("mimetype"), b"application/epub+zip")

    def test_send_requires_explicit_command_and_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "article.md"
            md_path.write_text(TEXT, encoding="utf-8")
            with mock.patch.object(tool, "fetch_markdown", return_value=("44", TEXT)), \
                 mock.patch.object(tool, "build_epub", return_value=Path(tmp) / "fake.epub"), \
                 mock.patch.object(tool, "send_to_kindle") as send:
                code = tool.main(["all", "https://x.com/a/status/44", "--out-dir", tmp])
            self.assertEqual(code, 0)
            send.assert_not_called()
            with self.assertRaises(tool.ImportError_):
                tool.send_to_kindle(md_path)

    def test_send_calls_kindlemcp_only_with_epub(self):
        with tempfile.TemporaryDirectory() as tmp:
            epub = Path(tmp) / "book.epub"
            epub.write_bytes(b"fixture")
            with mock.patch.object(tool.shutil, "which", return_value="/bin/kindlemcp-send"), \
                 mock.patch.object(tool.subprocess, "run") as runner:
                tool.send_to_kindle(epub, "My book")
            self.assertEqual(runner.call_args.args[0][0:3], ["kindlemcp-send", "--title", "My book"])


if __name__ == "__main__":
    unittest.main()
