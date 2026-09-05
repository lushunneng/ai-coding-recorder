# AICR Codex 生产级代码生成执行手册

## 目的

你是 AICR 项目的实现工程师。必须严格依据同目录的 `任务：设计并开发_AI_Coding_Recorder（AICR）.md` 生成生产级 Python 项目。该方案是唯一产品和架构依据；本手册规定执行顺序和质量门槛。

## 总规则

1. 先读完整主方案，再检查环境、目录和 Git 状态。
2. 未完成 Phase 0 交付物，不得编写业务实现。
3. 不猜测 Claude、Codex 或其他 Provider 的原生格式；未验证能力必须返回 `unsupported`。
4. 不获取或推断隐藏 Chain of Thought。
5. Raw JSONL 是唯一事实源，任何派生失败不能丢失 Raw。
6. 不修改用户项目文件，不记录完整环境变量，不上传数据。
7. 每次修改前先说明目标；每个阶段结束必须测试、检查、提交并报告。
8. 遇到方案冲突时停止相关实现，记录冲突并以主方案为准，不自行扩大范围。

## Phase 0：环境和协议冻结

执行只读检查：操作系统、Python 3.12+、uv、Git、PTY、SQLite WAL/FTS5、Git 命令和已安装 Agent。检查仓库与工作区状态，不覆盖用户改动。

必须生成并提交：

- `docs/schema.md`：Raw/Semantic Event 字段类型、状态机、Asset 分片、版本规则。
- `docs/capability_matrix.md`：pty/native/import 能力、字段保证和 confidence 上限。
- `docs/exit_codes.md`：Agent、Recorder、配置、恢复、导出错误码。
- `docs/architecture.md`：模块边界、数据流、热路径与派生路径。

Phase 0 只允许文档和测试夹具，不写 Provider 猜测逻辑。完成后运行 `git diff --check`、Ruff（如已配置）和文档链接检查，提交：

```text
docs: freeze AICR protocols and capability matrix
```

## Phase 1：Generic PTY 可靠记录

按 src layout 建立 Python 包和 Typer CLI。实现配置、日志、目录权限、Session 状态、锁、Raw JSONL writer、PTY 转发、进程组、信号、SIGWINCH、窗口尺寸、退出码和 recover。

硬性实现要求：

- 记录进程只写 `raw.jsonl`，不写 SQLite、不做 FTS、不渲染。
- 单写入器生成 sequence；每行独立 JSON；chunk flush，关键事件 fsync。
- Raw Event 只使用精简字段；非 UTF-8 使用 base64。
- lock 使用 pid、process_start_time、heartbeat 和 takeover_id；stale 接管使用原子 CAS rename。
- 使用 `setsid` 和独立进程组；Ctrl+C/SIGTERM/SIGHUP 转发有超时和清理路径。
- 子 shell 启动序列纳入记录；支持 `--norc --noprofile` 的用户命令。
- raw 尾行损坏不得静默修复原文件；`recover` 只写 recovery metadata，`--scan` 记录 skipped sequences。

必须测试 bash 交互、Unicode、ANSI、非 UTF-8、Ctrl+C、Ctrl+D、SIGTERM、SIGWINCH、非零退出、kill -9、损坏尾行、陈旧锁、并发 Session、磁盘/权限错误和内存有界性。

通过后提交：

```text
feat(recorder): add reliable generic pty recording
```

## Phase 2：查看、导出和最小导入

实现 Semantic Event 派生、`sessions`、`show`、JSON/Markdown/HTML/Bundle、Asset 重组、脱敏、原子导出和 `import --transcript`。

要求：

- events.jsonl 从 raw.jsonl 派生；派生失败不影响 Raw。
- Semantic Event 才包含 actor、provider、capture_mode、stream、confidence 等扩展字段。
- PTY `stream=merged`；Generic 语义 confidence 不得高于 `observed`。
- Asset 用 chunk_of、chunk_index、chunk_total 重组并校验 SHA-256。
- 默认文件名为 `{session_id[:8]}_{started_at:%Y%m%dT%H%M%S}.{ext}`。
- 导出写临时文件后原子 rename；已有文件需 `--force`。
- HTML 默认 `script-src 'none'`；需要脚本时使用构建所得 sha256 CSP。
- 所有日志内容 HTML 转义，默认脱敏；JWT 默认整体替换，`--deep-redact` 不落盘解码结果。
- Bundle 提供 manifest、版本、校验值和脱敏状态。

测试并发导出、超大输出、缺片、恶意 HTML、脱敏误报回归、重复导入和导出失败不损坏 Raw。提交：

```text
feat(export): add safe renderers and transcript import
```

## Phase 3：SQLite 派生索引

实现 migrations、sessions/events 表、外键、唯一约束、索引、WAL、busy timeout、幂等 upsert、`rebuild-index` 和 FTS（可用时）。SQLite 写入只在 session_end 后或后台执行，不进入 PTY 热路径。重建跳过正在写入的 Session，并可重复执行。

测试 SQLite 删除、损坏、锁竞争、并发 Session、重复重建和结果一致性。提交：

```text
feat(storage): add rebuildable sqlite index
```

## Phase 4：Git 与维护

实现 Git 前后快照、超时、大小限制、非 Git warning、`delete`、`prune --dry-run/--yes`、retention_days 和 max_sessions。禁止自动删除历史数据。

测试非 Git 目录、超大 diff、二进制 diff、权限失败、保留策略和删除确认。提交：

```text
feat(maintenance): add git capture and retention controls
```

## Phase 5：Native Provider Adapter

一次只实现一个已验证 Provider。提交验证清单、版本范围、脱敏 Fixture、事件映射、未知字段策略、损坏文件行为、重复导入测试和端到端导出测试。验证不完整时保留 `unsupported`，Generic PTY 仍可用。禁止凭网络文章或猜测目录实现解析器。

## Phase 6：搜索和外部控制

SQLite FTS5 可用时实现搜索和过滤；不可用时给明确提示。只有外部 control socket/file 经过安全和并发测试后，才考虑快捷导出。不得通过 PTY 拦截用户输入实现 `/aicr-export`。

## 每次提交前检查

```bash
pytest
ruff check .
ruff format --check .
python -m mypy src  # 若项目启用 mypy
python -m compileall src
 git diff --check
git status --short
```

测试失败不得提交。若某工具未安装，记录原因并执行可用替代检查，不得伪造通过。

## 代码质量要求

使用清晰类型标注、Protocol/抽象接口和小模块；异常必须可分类并保留上下文；文件写入使用原子替换；外部命令使用 argv，不拼接 shell 字符串；路径处理防止目录穿越；日志禁止秘密；测试不得依赖真实用户目录、真实密钥或网络。

## 阶段报告格式

每个 Phase 完成后报告：实现范围、文件变更、测试命令和结果、资源指标、已知限制、数据路径、回滚方式、Commit ID。未经用户确认，不进入下一个高风险 Provider 阶段。
