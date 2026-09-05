# AICR 唯一主实施方案

> 本文是 AICR 唯一产品、架构、开发和验收依据。

## 产品目标

AICR 是 Local-first 的 AI Coding Agent 会话记录器：从启动命令开始保存本机可观察的终端过程，并按需导出 Markdown、HTML、JSON 和 Bundle。不上传数据、不调用模型、不需要账号。JSONL 是事实来源，SQLite 和渲染结果可删除后重建。

## 能力边界

- pty：保证终端输入尝试、合并后的终端字节流、生命周期和退出码；不保证 stdout/stderr 分离、完整 Prompt、Tool Call 或文件编辑。
- native：仅支持已检查版本和已验证字段的 Provider 语义事件。
- import：保存用户提供文件及来源；普通文本不得猜测隐藏语义。

PTY 中 stdout/stderr 通常合并，事件不得伪装成可靠的 stdout/stderr。输入可能因 TTY echo 重复。只记录用户可见内容和明确可观察行为，不获取隐藏 Chain of Thought。

## 推荐使用

```bash
aicr record -- claude
aicr record -- codex --model gpt-5
aicr record -- bash
aicr sessions --limit 20
aicr show latest
aicr export latest --format markdown --out ./session.md
aicr export latest --format html --out ./session.html
aicr export latest --bundle --out ./session.zip
```

命令在 -- 后按原始 argv 传递。直接启动的 Agent 无法事后追溯终端，应使用 Agent 导出后 import。未验证格式返回 Unsupported Provider History。首版不实现 /aicr-export，后续使用 Unix socket 或 control file 外部控制。

## CLI 合同

提供：--help、--version、doctor、record、sessions、show、export、import、recover、rebuild-index、providers。--bundle 与 --format 互斥；--open 仅 HTML；默认输出 ~/.aicr/exports/；已有文件默认拒绝，覆盖需 --force；latest 按 started_at 和 session_id 确定性排序；Agent 退出码原样返回，Recorder 错误使用独立错误码。普通命令自动初始化，保留 init 修复目录和权限。

## 存储和事件

默认 ~/.aicr/，可用 AICR_HOME 覆盖。目录权限 0700，文件 0600。Session 包含 raw.jsonl、events.jsonl、metadata.json、lock 和 assets/。首版事件为 session_start、terminal_input、terminal_output、process_exit、session_end、error、warning。事件必须包含 schema_version、id、session_id、sequence、timestamp、monotonic_ns、type、actor、provider、capture_mode、stream、payload、is_partial、content_ref、confidence。非 UTF-8 使用 base64。Session 状态为 running -> completed、failed 或 interrupted。

## 可靠性

单一写入器生成 sequence；JSONL 按完整行追加，chunk flush，开始/结束/错误 fsync。大输出写入 assets 并记录路径、大小、SHA-256。每个 Session 加锁；导出读取最后完整 JSON 行形成快照，临时文件写完后原子 rename。磁盘满、权限错误或 Asset 失败时继续写生命周期和 error，并标记 degraded。recover 验证 JSONL、截断损坏尾行、检查 sequence、补写结束事件并标记 interrupted。rebuild-index 从 JSONL 幂等重建 SQLite。独立进程组处理 Ctrl+C、SIGTERM、EOF、SIGWINCH 和窗口尺寸变化。默认限制：单事件 1 MiB、单 Asset 64 MiB、单 Session 2 GiB、总目录 20 GiB，均可配置。

## 隐私和导出

原始 JSONL 不修改；导出默认脱敏，至少覆盖 API Key、GitHub/AWS Token、Bearer、JWT、密码和私钥，并记录规则版本、命中类型和数量。--include-raw 仅 Bundle 生效，显示警告并要求确认。HTML 对日志内容做转义，禁止脚本执行，资源本地内置；大 Session 使用折叠和分段。

## Git 和 Provider

Git 在开始和结束捕获 branch、HEAD、status、diff 摘要和文件统计，设置超时和大小上限；非 Git 或 Git 失败仅 warning。GenericAdapter 首先实现；Claude/Codex 只有在本机检查版本并有脱敏 Fixture 后启用 native，其他 Provider 未验证时为 unsupported 但可用 pty。

## 开发阶段

1. Phase 0：检查环境，冻结 schema、状态、权限、配额、退出码和能力矩阵。
2. Phase 1：Generic PTY、raw JSONL、metadata、锁、信号、resize、recover。
3. Phase 2：sessions/show、JSON/Markdown/HTML/Bundle、脱敏和原子导出。
4. Phase 3：SQLite migrations、索引、幂等 upsert、rebuild-index。
5. Phase 4：Git、transcript import、hash 去重。
6. Phase 5：经过验证的 Native Adapter。
7. Phase 6：FTS 搜索和外部控制。

每阶段必须通过 pytest、Ruff、类型检查、故障测试和人工 CLI 验收后再进入下一阶段。

## 最低验收

覆盖 Unicode、ANSI、非 UTF-8、Ctrl+C/Ctrl+D、SIGTERM、resize、非零退出、kill -9、损坏尾行、磁盘满、并发 Session/导出、超大输出、恶意 HTML、默认脱敏、SQLite 重建、Git 非仓库和未验证 Provider。

## 明确不做

隐藏思维链、云同步、账号、服务端、实时 Web、未经验证解析器、目录扫描推断、完整环境变量、会话内输入拦截和首版加密存储。

## 实施细则

### 首次运行与配置

首次执行 `record`、`sessions`、`export` 或 `doctor` 时创建 `AICR_HOME`、默认配置、日志目录和权限。配置文件支持数据目录、脱敏开关、是否记录输入、事件/Asset/Session/总容量限制、日志级别和保留策略。配置错误必须指出文件、字段和修复方式，不得静默使用危险默认值。

### PTY 记录流程

1. 校验命令存在、当前终端可用并创建 Session 目录和锁。
2. 写入 `session_start`，保存 argv、cwd、终端类型和初始窗口尺寸，不保存完整环境变量。
3. 创建独立进程组和 PTY，双向转发输入输出；所有字节先进入 raw.jsonl，再尝试生成标准事件。
4. 监听窗口变化和终止信号，保证子进程退出后关闭 PTY、写入 `process_exit` 和唯一的 `session_end`。
5. 原子更新 metadata，释放锁并打印结果。

### 失败降级

记录失败分为 `normal`、`degraded`、`failed`、`interrupted`。SQLite、Git、Renderer 或单个 Asset 失败不能删除 raw.jsonl。发生磁盘满、权限变化、写入延迟或数据截断时，必须写入可写的错误事件；若 raw.jsonl 也无法写入，终端显示明确告警并在 metadata 中尽力记录。

### 数据一致性

事件 `id` 全局唯一，`session_id + sequence` 唯一。JSONL 每行必须可独立解析；恢复时只接受完整行。导入保存源文件 SHA-256、Provider、版本、Adapter 版本和导入时间，重复导入默认提示已存在。SQLite 使用 migration version、外键和幂等 upsert，重建结果必须可重复。

### 导出安全

导出先生成内存有界的事件迭代器，再写临时文件并原子替换目标。Markdown 使用 fenced code block；HTML 对文本、属性和链接分别转义并设置严格 CSP。超长输出显示摘要和折叠内容，原始 Asset 仍保留。Bundle 内提供 manifest，列出文件、校验值、是否脱敏和生成版本。

### 观测与维护

日志采用轮转，禁止写入 Token、密码和完整环境变量。`doctor` 检查 Python、PTY、目录权限、磁盘空间、SQLite/FTS5、Git 和 Provider 能力。提供 `recover`、`rebuild-index`、`sessions --status running` 和 `delete`，让用户能发现、修复和清理长期积累的数据。

### 测试门槛

单元测试覆盖事件校验、状态机、脱敏、路径和配置；集成测试覆盖 record 到 export 全链路。故障测试必须注入尾行损坏、kill -9、磁盘满、权限拒绝、并发导出、超大输出和 SQLite 损坏。CLI 验收至少包含 bash、Unicode、ANSI、非 UTF-8、Ctrl+C、Ctrl+D、SIGTERM、SIGWINCH、非零退出和非 Git 目录。

### 版本与兼容

事件 `schema_version` 与 Adapter 版本独立管理。读取旧版本时提供迁移或明确拒绝；不得静默丢字段。每次协议变更更新 CHANGELOG、Fixture 和迁移测试，导出文件写入生成器版本和规则版本。

### 交付出口

Phase 1 只有在“可记录、可恢复、内存有界、退出码正确”全部通过后结束；Phase 2 只有在“导出安全、并发稳定、原始文件不受影响”通过后结束；Provider 阶段必须逐个 Provider 验证，任何未验证能力保持 unsupported。每阶段产出测试报告、资源指标、已知限制和回滚方式。

## 审查修订决策

### 文件关系

`raw.jsonl` 是唯一事实源，只追加、不改写。`events.jsonl` 是从 raw.jsonl 派生的规范化缓存，不是可靠写入前提；其写入失败只记录 warning，不阻断 raw。`rebuild-index` 同时可从 raw 重建 events 和 SQLite。导出默认读取 events，缺失或版本不兼容时直接从 raw 生成临时规范化流。

### CLI 补充

增加：

```text
aicr delete <SESSION_ID|latest> [--include-assets] [--yes]
aicr sessions [--cursor TOKEN] [--limit N]
aicr show <SESSION_ID|latest> [--format summary|transcript|json] [--errors] [--from SEQ] [--to SEQ]
```

`show` 默认输出适合终端阅读的摘要和按时间线排列的可观察事件；`--format transcript` 输出分页友好的纯文本，`--format json` 输出机器可读 JSON。`delete` 先删除派生索引，再删除 Session 目录；`--include-assets` 明确删除大输出，删除前需 `--yes` 或交互确认，禁止自动删除最旧数据。

配置格式固定为 TOML，默认路径 `~/.aicr/config.toml`，可由 `AICR_HOME` 覆盖。

### 恢复与锁

`recover` 不修改 raw.jsonl。它验证并记录最后一个完整行序号，在 metadata 写入 `recovery.last_valid_sequence`、`truncated_tail=true` 和 `interrupted` 状态；导出和重建只读取有效行。必要时另写 `recovered.jsonl`，原始文件保持只追加。

lock 文件使用 JSON 保存 `pid`、`process_start_time`、`session_id`、`created_at`、`heartbeat_at` 和主机标识。获取锁时先检查 PID 是否仍存在且启动时间匹配；进程不存在或心跳超过 30 秒才可标记 stale，接管前写入 warning。正常进程每 5 秒更新心跳，不能仅凭固定年龄判定陈旧。

总目录达到 20 GiB 时默认拒绝新录制并给出清理路径；当前 Session 已运行时继续写生命周期和错误，标记 `degraded`，不自动删除历史 Session。用户可显式执行 delete 或调整配额。

SQLite 启用 WAL、busy timeout 和外键。多个 Session 可并发追加其 JSONL，但索引写入遇到锁时重试并退避。`rebuild-index` 对每个 Session 获取读锁，跳过仍在写入的尾部并在完成后可再次运行，不删除 raw。

### 事件字段定义

Generic PTY 的 `stream` 固定为 `merged`；Native Adapter 可使用 `stdout`、`stderr`、`stdin` 或 Provider 定义的流。`confidence` 是枚举：`confirmed`（来源明确且 Fixture 验证）、`observed`（直接观察但语义有限）、`inferred`（仅允许在明确规则下使用）、`unknown`（无法判断）。Generic PTY 的语义事件不得高于 `observed`。

大输出阈值固定为 256 KiB：内容超过阈值写入 Asset，事件 payload 只保留摘要和引用；单事件 1 MiB 是 metadata 和内联 payload 的硬上限，单 Asset 64 MiB，超过 Asset 上限分片保存。

### 脱敏规则

JWT 先识别完整三段式字符串并整体替换；默认不解码 payload，以避免性能和误报问题。可选 `--deep-redact` 在内存中解码 payload 后扫描字段，绝不保存解码结果。`redaction_debug` 默认关闭；开启时仅记录规则名称和字符 offset，不记录原始匹配值。

### 阶段调整

Phase 2 提前实现最小 `import --transcript`，确保直接启动会话的基本工作流可用；Provider Native Adapter 仍在 Phase 5。Phase 2-3 期间 Native import 属于已知限制。

### 进程组与信号

Linux/macOS 使用 `setsid` 创建独立 session，并在子进程组内转发终端信号；Recorder 保留控制终端，收到 Ctrl+C 后向子进程组发送 SIGINT，收到 SIGTERM 时先转发并等待，再按超时发送 SIGKILL。SIGHUP 按同一清理路径处理。SIGWINCH 通过 ioctl 更新 PTY 尺寸。

### HTML CSP

目标 CSP：`default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'`。Bundle 内资源使用相对路径，禁止 CDN 和内联脚本执行日志内容。

### Provider 验证清单

启用 native 前必须提交：Provider 名称和版本范围、历史格式样本来源、脱敏 Fixture 路径、解析事件类型清单、字段映射、未知字段保留策略、损坏文件行为、重复导入测试、版本不匹配行为和端到端 export 测试。验证结果写入 `providers/<name>/VERIFICATION.md`，未满足全部项目保持 unsupported。

## 第二轮架构修订（正式条款）

### 事件分层与热路径

`raw.jsonl` 使用精简 Raw Event，仅包含 `id`、`session_id`、`sequence`、`timestamp`、`monotonic_ns`、`type`、`payload` 七类字段；`events.jsonl` 保存派生的 Semantic Event，才扩展 actor、provider、capture_mode、stream、confidence、provider_data 等字段。PTY 记录进程只追加 raw.jsonl，不写 SQLite、不执行全文索引；events 和 SQLite 在 session_end 后同步生成或由后台任务生成，避免索引阻塞终端热路径。

### 锁接管协议

stale lock 接管采用 CAS：写入包含唯一 takeover_id 的临时 lock，使用原子 rename 覆盖旧 lock，随后读回校验 takeover_id；若不是自己的 takeover_id，当前进程让步并重试。lock JSON 包含 pid、process_start_time、session_id、created_at、heartbeat_at、host_id。只有 PID 不存在且心跳超过 30 秒才允许发起接管，不能仅凭文件年龄判断。

### Asset 分片协议

超过 256 KiB 的内容写入 Asset；超过单 Asset 64 MiB 时分片。每个分片事件必须包含 `content_ref`、`chunk_of`、`chunk_index`（从 0 开始）、`chunk_total`、字节数和 SHA-256。导出层按 `chunk_of` 聚合，按 `chunk_index` 排序并校验总数、大小和哈希后拼接；缺片时保留 warning 占位，不静默生成不完整内容。

### 恢复扫描

`recover` 默认只验证尾部并在 metadata 写入最后有效 sequence，不修改 raw.jsonl。`recover --scan` 扫描整个文件，跳过所有不可解析行，将其 sequence（若可识别）写入 `recovery.skipped_sequences`，并在派生 events 和导出时间线对应位置插入 warning 占位。原始文件始终只追加，任何恢复结果都可追溯。

### 容量与保留策略

总目录达到 20 GiB 时默认拒绝新录制；正在运行的 Session 继续写生命周期和 error，并标记 degraded。禁止自动删除历史数据。配置 TOML 中保留策略独立定义：`retention_days = null`、`max_sessions = null`，分别按时间和数量控制；触发时 doctor 给出摘要，`aicr prune --dry-run` 列出待删 Session，实际清理必须显式 `aicr prune --yes`。

### SQLite 并发

SQLite 启用 WAL、外键和 busy timeout。JSONL 记录进程完全不触碰 SQLite；session_end 后再写索引，失败可重试。`rebuild-index` 按 Session 读锁处理，跳过正在写入的 Session，完成后可重复执行。

### 导出 CSP 与脱敏版本

单文件 HTML 默认使用 `script-src 'none'`；需要交互脚本时只允许构建阶段计算出的 `script-src 'sha256-<hash>'`，禁止使用 `script-src 'self'` 放宽策略。内置样式可使用 `style-src 'unsafe-inline'`，图片使用 `img-src data:` 或 Bundle 相对路径。

脱敏规则有独立的 `redaction_rules_version`，与 schema_version 分开递增。每条规则至少包含一个 match fixture 和一个 non-match fixture；规则变更必须通过全量回归。`redaction_debug` 仅记录规则名和 offset，不记录原文；环境变量形式如 `export AWS_SECRET=...` 纳入覆盖范围。JWT 默认只整体识别三段式字符串；`--deep-redact` 才在内存中解码 payload 并扫描，解码结果不落盘。

### CLI 和默认文件名

CLI 合同补充：

```text
aicr init [--force]
aicr show <ID|latest> [--format summary|transcript|json] [--from SEQ] [--to SEQ] [--since ISO|30m] [--until ISO|30m]
aicr delete <ID|latest> [--include-assets] [--yes]
aicr prune [--dry-run] [--yes]
aicr sessions [--cursor TOKEN] [--limit N]
```

`--from` 和 `--to` 只接受 sequence 整数；时间筛选使用 `--since` 和 `--until`。`show` 默认输出终端友好的摘要和事件时间线，transcript 输出分页友好的纯文本，json 输出机器可读结构。`init` 负责创建/修复目录、默认 config.toml 和权限；`doctor` 只检查，不修改。

未指定 `--out` 时默认文件名为 `{session_id[:8]}_{started_at:%Y%m%dT%H%M%S}.{ext}`，Bundle 使用 `.zip`；目标存在时拒绝，除非 `--force`。

### Phase 0 交付物

Phase 0 必须提交以下文件后才算完成：

- `docs/schema.md`：所有 Raw/Semantic 事件、字段类型、版本规则和分片协议。
- `docs/capability_matrix.md`：各 capture_mode 支持的字段及 confidence 上限。
- `docs/exit_codes.md`：Agent、Recorder、配置、恢复和导出错误码。

Phase 2 的正式定义为：`sessions/show`、JSON/Markdown/HTML/Bundle、脱敏、原子导出和最小 `import --transcript`；这是将原 Phase 4 的基础导入前移，以保证直接启动会话也有可用保存路径。Native Adapter 仍在 Phase 5。

### Shell 启动行为

PTY 子进程继承 shell 的启动序列，`.bashrc`、`.profile` 等初始化输出会进入 raw.jsonl；需要干净环境时使用 `aicr record -- bash --norc --noprofile`。脱敏规则覆盖常见 `export NAME=secret` 形式，但不能替代用户避免在终端输入秘密。
