# X Article → Kindle / KOReader

本目录是 Kindle 项目的桌面伴随工具，基于公开 X（Twitter）文章、作者连续长帖和普通帖子生成可离线阅读的 EPUB。无需改动设备上现有的 `SimpleUI` 或 `sendtophone.koplugin`。

## 先安装

- Python 3.10+ 
- [Pandoc](https://pandoc.org/installing.html)，用于生成 EPUB3，需在终端可执行 `pandoc`
- 可选 [kindlemcp](https://pypi.org/project/kindlemcp/)：`pipx install kindlemcp`，用于通过 Amazon 邮件发送 Kindle
- 可选 [x2md](https://github.com/yshmarov/x2md)：`pipx install git+https://github.com/yshmarov/x2md`，仅在显式指定 `--provider x2md` 时使用

## 使用

在仓库根目录运行：

```sh
# 只抓正文，生成 articles/x-<id>.md
python tools/x_to_kindle.py fetch "https://x.com/author/status/1234567890"

# 抓取、下载正文内的图片并封装 EPUB
python tools/x_to_kindle.py all "https://x.com/author/status/1234567890"

# 将已有 Markdown 转成 EPUB，可单独指定目标
python tools/x_to_kindle.py epub articles/x-1234567890.md --output books/article.epub

# 仅在明确要求发送时，才通过邮件投递 Kindle
python tools/x_to_kindle.py all "https://x.com/author/status/1234567890" --send

# 已存在 EPUB 时单独发送
python tools/x_to_kindle.py send articles/x-1234567890.epub --title "文章标题"

# x2md 手动回退，注意无法保证抓取整条作者 Thread
python tools/x_to_kindle.py fetch "https://x.com/author/status/1234567890" --provider x2md
```

## 工作流程

1. **抓取**：默认调用公开的 [Xtracticle Markdown API](https://xtracticle.com/mcp-server) (`https://xtracticle.com/api/markdown/{post-id}`)，请求 `thread=1` 和 `front_matter=1`，保存完整原始 Markdown。仅支持公开 `/status/<数字ID>` 链接。X 的 `/i/article/` 阅读器链接需在 X 中获取对应帖子分享链接。
2. **转换**：Pandoc 生成 EPUB3。图片从 X 官方静态资源域下载后嵌入 EPUB，使其可在 KOReader 离线显示。抓图失败默认报错并停止；只有显式设置 `--allow-missing-images` 才允许生成缺图文档。
3. **传输**：
   - **KOReader 用户首选**：保留 `.epub` 文件，通过 USB、LocalSend 或 Calibre 传输到 Kindle，在 KOReader 中打开。
   - **Kindle 原生阅读器**：先通过 kindlemcp 设置邮件和 Kindle 地址，并在 Amazon 个人文档设置中添加获准发送者，然后用 `--send` 或 `send` 子命令投递。

默认只生成 EPUB，不会自动发邮件，也不会修改 KOReader。公开 X 抓取服务可能限流或发生格式变更；不公开、已删除或受限帖子无法抓取。

## 技术边界

- 仅抓取 `x.com`、`twitter.com` 的合法状态链接；图片下载限制在 X 官方图片资源域，防止外部重定向访问任意地址。
- 正文最大 4 MiB，单图 12 MiB，全部图片 48 MiB，最多 60 张，避免恶意超大内容。
- 邮件凭证只通过 kindlemcp 的本机配置或环境变量传入，不加入 Git 仓库。
- 正文与来源文件保留在本地 `articles/`，请勿将含私人信息或版权内容的导出文件提交到公开仓库。
- 图片、复杂图表、引用和排版需要在真实 X Article 上人工核对；当前离线测试不等同于真机验证。

## 验证

```sh
python -X utf8 tests/test_x_to_kindle.py
```

GitHub Actions 的 `X Article to Kindle checks` 在 PR 中单独运行此离线回归测试，完全不会真实发送邮件。SimpleUI 原有打包脚本依旧只收录 `main.lua` 与插件目录，不会把这个桌面工具装入 Kindle 插件包。

## 后续可迭代

- 多篇合集 EPUB、重复链接去重、来源与作者索引。
- 基于本地文件夹的简单“待同步”目录和 OPDS。
- MCP 适配层和 Codex Skill，分别包装抓取、转书、发送三个动作。
