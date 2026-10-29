# SimpleUI 个人版

基于 Doctor Hetfield 的上游 **3.0.1**（已同步至上游 main `71ed399`，2026-10-29），个人版本 **3.0.1-personal.1**。
[个人分支](https://github.com/dhhp2k1/simpleui.koplugin/tree/personal/pw5) ·
[下载安装包](https://github.com/dhhp2k1/simpleui.koplugin/releases) ·
[原版项目](https://github.com/doctorhetfield-cmd/simpleui.koplugin)

保留原版界面与配置能力，未加入 AI 或资讯。目标设备为 Paperwhite 5、固件
5.16.2.1.1；需要 KOReader 2026.03+ 和自带 CoverBrowser 插件。
已在 PW5、固件 5.16.2.1.1、KOReader 2026.07.1 上完成开关书籍、休眠唤醒、
隐藏恢复与批注保留，以及 LocalSend 收书后的书库分页验收。

验证范围与已知限制见 [实机验证记录](docs/DEVICE_VALIDATION.md)。

## 3.0.1-personal.1 实机修复

- 书库页码在首页数据重建后保留；隐藏、恢复不再跳回第一页。
- 末页缩短时退到最后一个有效页，不跳到第一页。
- 新书检测使用包含隐藏文件的磁盘清单，恢复显示不会误判为新书到达。
- 首页网格复用缓存时，也会在下次重建前检查未见过的文件，支持 LocalSend 等无事件收书。
- 恢复显示后立即提示书名；修复首次向导无法构建预设列表的导出遗漏。

新书不会在传输完成瞬间强制重绘屏幕；翻页、切回首页或看书返回后的下次重绘才更新。
不增加定时检查，用户选择的其他排序和普通分页继续保留。

## 改动

- 平铺书库未设置排序时默认按文件日期从新到旧，已保存的排序继续生效。
- 日期相同的书籍保持确定顺序。
- 最近加入排序下，检测到新增文件才回到第一页；普通翻页、删书和隐藏保持分页。
- 长按书籍可“从首页和书库隐藏”，在 SimpleUI 设置 → 书库 → 已隐藏的书籍与文档中恢复。
- 隐藏只影响 SimpleUI 展示和它接管的书库列表，保留书籍、批注和阅读历史。
  Kindle 原生书库与其他文件选择器仍可访问文件。外部移动、改名后，隐藏记录需手动恢复。
- 隐藏记录纳入书库设置备份。个人版更新器仅读取此 fork 的个人版本，支持数字版本后缀。
- 更新器连不上 GitHub 下载服务器时，依次改用 gh-proxy.com、ghfast.top、ghproxy.net
  镜像下载，并用 GitHub API 给出的 SHA-256 校验安装包；拿不到校验值时不使用镜像。

日期排序使用文件修改时间，复制工具保留旧时间时，显示顺序也会保留该时间。
新默认排序只作用于“平铺书库”组件，已有首页布局不强制改写。

## 安装

1. 从 Releases 下载 `simpleui.koplugin.zip` 和 `SHA256SUMS`，不要使用 Source code ZIP。
2. 退出 KOReader 再连接 USB。已有 SimpleUI 时，先备份插件目录与
   `koreader/settings/simpleui`。
3. 解压，将 `simpleui.koplugin` 放进 `koreader/plugins/`。确认路径为
   `koreader/plugins/simpleui.koplugin/main.lua`，没有多套一层目录。
4. 安全弹出设备并启动 KOReader，首页添加“平铺书库”。已有排序偏好时，
   在组件设置中手动选择“加入日期（最新）”。
5. 回滚时，退出 KOReader，恢复备份的插件和设置。

## 实机检查

- 连续打开、关闭两本书，检查首页、底栏、进度和休眠唤醒。
- 在平铺书库第二页后加入 EPUB，刷新后确认回到第一页。
- 隐藏、恢复一本书，确认书籍和批注完整。
- 切换标题排序再传书，确认排序选择和分页保持。
- 异常时先恢复备份，再查看 `koreader/crash.log`。

## 开发与构建

```sh
python -m pip install -r requirements-dev.txt
python -X utf8 tests/test_hidden_books.py
python -X utf8 tests/test_arrivals.py
python -X utf8 tests/test_personal_runtime.py
python -X utf8 tests/test_device_regressions.py
python -X utf8 scripts/package_personal.py
```

CI 在 Windows、Linux 执行相同检查，安装包输出到 `dist/`。
main 保留上游代码，个人改动在 personal/pw5。
许可和来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
[上游说明](docs/UPSTREAM_README.md)完整保留。
