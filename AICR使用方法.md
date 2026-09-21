# AICR 使用方法

本文档介绍 AI Coding Recorder（AICR）的安装、初始化、日常录制、会话查看、Markdown 导出、数据恢复、维护和跨平台使用方法。

AICR 将终端中的 Agent 交互记录到本地，原始数据保存在本机，不依赖云端服务。当前版本为 `0.1.0`。

## 1. 使用前提

AICR 当前要求：

- Python `3.12` 或更高版本；
- Git；
- Linux 或 macOS 的 Unix PTY 环境；
- 要记录的 Agent 命令已经安装并且能够直接运行。

常见 Agent 命令包括：

```bash
claude --version
codex --version
gemini --version
```

如果命令不存在，AICR 不能替你安装 Agent。应先单独安装并验证 Agent，再使用 AICR 录制。

### Windows 说明

当前录制实现依赖 Unix PTY。Windows 原生 PowerShell 和 CMD 不属于当前推荐运行环境，建议使用 WSL2 Ubuntu：

```powershell
wsl --install -d Ubuntu
```

安装完成后打开 Ubuntu 终端，按照本文的 Linux 步骤操作。Agent 也应安装在 WSL 环境中，并在 WSL 内确认：

```bash
command -v claude
claude --version
```

## 2. 获取代码

SSH 方式：

```bash
git clone git@github.com:lushunneng/ai-coding-recorder.git
cd ai-coding-recorder
```

HTTPS 方式：

```bash
git clone https://github.com/lushunneng/ai-coding-recorder.git
cd ai-coding-recorder
```

如果 SSH 报权限错误，使用 HTTPS，或者先将本机 SSH 公钥添加到 GitHub。

## 3. 首次安装

以下命令在一台电脑上通常只需要执行一次：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

这些命令的作用是：

1. 创建项目专用 Python 虚拟环境；
2. 激活虚拟环境；
3. 更新 pip；
4. 以可编辑模式安装 AICR。

`pip install -e .` 是可编辑安装。以后修改或拉取项目源代码时，通常不需要重新安装；只有依赖或 `pyproject.toml` 发生变化时才需要再次执行。

初始化 AICR 数据目录：

```bash
aicr init
```

默认数据目录为：

```text
~/.aicr
```

检查安装：

```bash
aicr version
aicr doctor
```

预期可以看到版本号，以及 `python`、`pty`、`home_exists`、`home_writable`、`config` 等检查项。

## 4. 每次使用前做什么

如果当前终端没有激活虚拟环境，每次使用前执行：

```bash
cd ~/01-Projects/Ai-Coding-Recorder
source .venv/bin/activate
```

然后即可使用：

```bash
aicr claude
```

如果已经把 AICR 安装到用户 PATH 中，也可以直接执行 `aicr`。判断方法：

```bash
command -v aicr
aicr version
```

如果 `command -v aicr` 找不到命令，先进入项目目录并激活 `.venv`。

退出当前终端后，虚拟环境不会自动保持激活，但不需要重新创建 `.venv`，只需再次执行 `source .venv/bin/activate`。

## 5. 启动录制

### 录制 Claude Code

推荐使用快捷命令：

```bash
aicr claude
```

等价写法：

```bash
aicr record -- claude
```

### 录制任意交互式命令

```bash
aicr record -- bash
aicr record -- zsh
aicr record -- codex
aicr record -- gemini
```

带参数时，将完整命令放在 `--` 后：

```bash
aicr record -- claude --continue
aicr record -- bash --norc --noprofile
```

子进程会继承完整的 Shell 启动流程。`.bashrc`、`.profile` 或其他启动脚本产生的输出也会进入记录。如果需要尽量干净的 Shell 环境，可以使用：

```bash
aicr record -- bash --norc --noprofile
```

### 录制过程中的注意事项

- AICR 会接管当前终端的 PTY，并把输入转发给 Agent；
- 不要在录制期间再启动第二个 AICR 进程来操作同一个会话；
- 可以正常输入问题、确认、命令和快捷键；
- 终端输入可能包含敏感信息，导出时会进行脱敏，但原始 `raw.jsonl` 仍应按敏感数据保护；
- 不要把 `~/.aicr` 提交到 Git 或上传到公共位置。

## 6. 正确结束录制

启动 `aicr claude` 后，进入的是 Claude Code 的交互界面。完成工作后，在 Claude 内输入：

```text
/exit
```

或者使用 Claude Code 支持的退出快捷键。

退出 Claude 后，AICR 会等待子进程结束、写入结束事件并返回 Shell。看到类似以下结果后，说明录制进程已经结束：

```text
session_id=...
```

不要直接关闭终端或使用 `kill -9` 作为正常退出方式。强制终止可能导致最后一段输出不完整，需要之后执行恢复检查。

## 7. 查看会话

列出最近 20 个会话：

```bash
aicr sessions
```

指定数量：

```bash
aicr sessions --limit 50
```

按状态查看：

```bash
aicr sessions --status completed
aicr sessions --status running
aicr sessions --status failed
```

使用游标继续查看下一页：

```bash
aicr sessions --limit 20 --cursor <上一页最后一个session_id>
```

输出列依次为：

```text
session_id    status    provider
```

查看最新会话摘要：

```bash
aicr show latest
```

按会话 ID 查看：

```bash
aicr show <session_id>
```

查看终端转录：

```bash
aicr show latest --format transcript
```

查看 JSON：

```bash
aicr show latest --format json
```

`latest` 表示按开始时间选择最近的会话，也可以直接使用完整的 `session_id`。

## 8. 导出 Markdown

导出最新会话：

```bash
aicr export latest --format markdown
```

命令会输出生成文件的路径。默认文件写入：

```text
~/.aicr/exports/
```

默认文件名格式类似：

```text
bbffcbbf_20260916T142556.markdown
```

指定输出文件：

```bash
aicr export latest \
  --format markdown \
  --out ~/Desktop/claude-session.md
```

如果目标文件已存在，需要明确覆盖：

```bash
aicr export latest \
  --format markdown \
  --out ~/Desktop/claude-session.md \
  --force
```

导出指定会话：

```bash
aicr export <session_id> --format markdown
```

导出 JSON：

```bash
aicr export latest --format json
```

导出 HTML：

```bash
aicr export latest --format html
```

HTML 导出是单文件，内容不依赖外部 CDN。Linux 下可用浏览器打开：

```bash
xdg-open ~/.aicr/exports/<文件名>.html
```

macOS 下：

```bash
open ~/.aicr/exports/<文件名>.html
```

## 9. 一次完整使用示例

```bash
cd ~/01-Projects/Ai-Coding-Recorder
source .venv/bin/activate

aicr init
aicr claude
```

在 Claude 中完成工作后：

```text
/exit
```

回到 Shell 后：

```bash
aicr sessions --limit 5
aicr show latest
aicr export latest --format markdown
```

## 10. 数据目录结构

默认情况下，AICR 使用 `~/.aicr`：

```text
~/.aicr/
├── config.toml
├── exports/
├── index.sqlite3
└── sessions/
    └── YYYY/
        └── MM/
            └── DD/
                └── <session_id>/
                    ├── metadata.json
                    ├── raw.jsonl
                    ├── events.jsonl
                    └── assets/
```

文件作用：

- `config.toml`：本机配置；
- `raw.jsonl`：原始事实记录，属于重要数据；
- `events.jsonl`：从原始记录派生的语义事件；
- `metadata.json`：会话状态、Provider 和时间信息；
- `index.sqlite3`：查询和搜索索引，可重建；
- `assets/`：大输出内容；
- `exports/`：Markdown、HTML、JSON 和 Bundle 导出文件。

可以用环境变量把数据目录放到其他磁盘：

```bash
export AICR_HOME=/path/to/aicr-data
aicr init
```

查看当前使用的目录：

```bash
echo "${AICR_HOME:-$HOME/.aicr}"
```

## 11. 配置文件

配置文件位置：

```text
~/.aicr/config.toml
```

默认配置：

```toml
max_total_bytes = 21474836480
max_session_bytes = 2147483648
redaction_enabled = true
record_input = true
```

字段说明：

- `max_total_bytes`：所有会话允许占用的最大字节数，默认 20 GiB；
- `max_session_bytes`：单个会话允许占用的最大字节数，默认 2 GiB；
- `redaction_enabled`：导出时是否启用脱敏，默认 `true`；
- `record_input`：是否记录终端输入，默认 `true`；
- `retention_days`：按时间提示清理的保留天数，默认不启用；
- `max_sessions`：按会话数量提示清理的上限，默认不启用。

例如：

```toml
max_total_bytes = 53687091200
max_session_bytes = 4294967296
redaction_enabled = true
record_input = true
retention_days = 90
max_sessions = 500
```

修改配置后，用以下命令检查：

```bash
aicr doctor
```

`aicr init --force` 会重新写入默认配置，可能覆盖现有 `config.toml`，修改前请先备份。

## 12. 恢复和索引重建

检查并恢复 JSONL 文件：

```bash
aicr recover
```

扫描中段损坏并记录跳过的序号：

```bash
aicr recover --scan
```

恢复操作不会重写原始 `raw.jsonl`。如果会话曾被强制中断，优先执行：

```bash
aicr recover --scan
aicr rebuild-index
```

重建 SQLite 索引：

```bash
aicr rebuild-index
```

索引属于派生数据，丢失后可以重建；`raw.jsonl` 才是需要重点备份的事实来源。

## 13. 搜索历史记录

```bash
aicr search "关键词"
```

限制返回数量：

```bash
aicr search "关键词" --limit 50
```

搜索依赖本地 SQLite 索引。如果搜索结果异常，先运行：

```bash
aicr rebuild-index
```

## 14. 删除和清理

删除指定会话前，先确认会话 ID：

```bash
aicr sessions --limit 50
```

删除时必须显式确认：

```bash
aicr delete <session_id> --yes
```

会话目录中的原始记录、派生事件、元数据和 assets 会一起删除。删除是破坏性操作，重要会话应先导出 Markdown 或备份原始目录。

查看按数量策略将清理哪些会话：

```bash
aicr prune --dry-run
```

实际执行清理需要同时关闭 dry-run 并确认：

```bash
aicr prune --no-dry-run --yes
```

默认情况下不会自动删除历史会话。

## 15. 导出 Bundle

生成包含 HTML、Markdown 和清单的 Bundle：

```bash
aicr export latest --bundle
```

Bundle 默认写入 `~/.aicr/exports/`。

如果确实需要把原始 JSONL 一起打包，必须显式确认：

```bash
aicr export latest --bundle --include-raw --force
```

原始记录可能含有终端输入、路径、令牌或其他敏感信息。除非有明确需要，不建议携带 `--include-raw` 分享。

## 16. Provider 能力

查看当前 Provider：

```bash
aicr providers
```

通用 PTY 录制方式：

```bash
aicr record -- <agent-command>
```

即使某个 Agent 没有专用 Native Provider，也可以使用通用 PTY 记录终端交互。Native Provider 的解析能力取决于该 Provider 的版本、输入格式和适配器实现。

## 17. 故障排查

### 找不到 `aicr`

```bash
cd ~/01-Projects/Ai-Coding-Recorder
source .venv/bin/activate
pip install -e .
aicr version
```

### 找不到 Python 3.12

检查版本：

```bash
python3 --version
python3.12 --version
```

Linux 和 macOS 需要先安装 Python 3.12。Windows 请在 WSL Ubuntu 内安装。

### `pty: error` 或录制无法启动

运行：

```bash
aicr doctor
```

确认 `pty: ok`。如果在原生 Windows PowerShell 中运行，请改用 WSL2。

### Agent 命令找不到

```bash
command -v claude
claude --version
```

如果没有输出，先安装 Agent，或者用绝对路径录制：

```bash
aicr record -- /absolute/path/to/agent
```

### 会话显示为 `running`

先确认是否还有录制进程：

```bash
aicr sessions --status running
```

优先回到原终端，在 Agent 内正常执行退出。如果终端已经异常关闭，再运行：

```bash
aicr recover --scan
aicr rebuild-index
```

### Markdown 没有最新内容

确认录制进程已经结束，再导出：

```bash
aicr sessions --limit 5
aicr export <session_id> --format markdown --force
```

如果仍然异常：

```bash
aicr recover --scan
aicr rebuild-index
```

### 更新代码

```bash
cd ~/01-Projects/Ai-Coding-Recorder
git pull --ff-only origin main
source .venv/bin/activate
pip install -e .
aicr doctor
```

## 18. 备份建议

长期使用时，至少备份：

```text
~/.aicr/sessions/
~/.aicr/config.toml
```

可以先停止录制，再复制整个 AICR 数据目录：

```bash
cp -a ~/.aicr ~/aicr-backup
```

如果数据量较大，使用外部备份工具或定期备份到独立磁盘。分享记录时优先分享脱敏后的 Markdown 或 HTML，不要直接分享 `raw.jsonl`。

## 19. 推荐日常命令速查

```bash
# 激活环境
cd ~/01-Projects/Ai-Coding-Recorder
source .venv/bin/activate

# 检查
aicr version
aicr doctor

# 录制 Claude
aicr claude

# 查看会话
aicr sessions --limit 20
aicr show latest

# 导出 Markdown
aicr export latest --format markdown

# 搜索
aicr search "关键词"

# 恢复并重建索引
aicr recover --scan
aicr rebuild-index
```

