# AICR 项目的 Git 与 GitHub 使用指南

## 当前仓库记录

- 远端仓库：`git@github.com:lushunneng/ai-coding-recorder.git`
- 主分支：`main`
- 当前提交：`a9c0e6d docs: finalize AICR implementation plan`
- 提交身份：`greendev <greendev@126.com>`
- 本地 `main` 已跟踪 `origin/main`

本仓库目前包含 AICR 唯一主方案文件：

`任务：设计并开发_AI_Coding_Recorder（AICR）.md`

## 首次配置

安装 Git 后设置提交身份：

```bash
git config --global user.name "greendev"
git config --global user.email "greendev@126.com"
```

通过 SSH 使用 GitHub：

```bash
ssh-keygen -t ed25519 -C "greendev@126.com"
cat ~/.ssh/id_ed25519.pub
ssh -T git@github.com
```

将公钥添加到 GitHub 的 **Settings → SSH and GPG keys**。克隆仓库：

```bash
git clone git@github.com:lushunneng/ai-coding-recorder.git
cd ai-coding-recorder
```

## 日常工作流

查看状态：

```bash
git status
git branch -vv
git remote -v
```

开始工作前同步远端：

```bash
git switch main
git pull --ff-only origin main
```

查看改动：

```bash
git diff
git diff --staged
```

提交并推送：

```bash
git add <文件路径>
git commit -m "docs: update implementation plan"
git push origin main
```

提交信息建议使用类型前缀：`feat`、`fix`、`docs`、`test`、`refactor`、`chore`。

## 推荐分支协作

功能或文档改动建议使用独立分支：

```bash
git switch -c docs/update-guide
# 编辑并测试
git add .
git commit -m "docs: add GitHub usage guide"
git push -u origin docs/update-guide
```

随后在 GitHub 创建 Pull Request，检查通过后合并到 `main`。合并后清理分支：

```bash
git switch main
git pull --ff-only origin main
git branch -d docs/update-guide
git push origin --delete docs/update-guide
```

## 查看历史和版本

```bash
git log --oneline --decorate --graph --all
git show <commit>
git diff main..origin/main
git tag
```

发布稳定版本时可创建标签：

```bash
git tag -a v0.1.0 -m "AICR v0.1.0"
git push origin v0.1.0
```

## 常见问题

### 推送被拒绝

先同步并重试：

```bash
git pull --rebase origin main
git push origin main
```

如果出现冲突，解决文件中的冲突标记后执行：

```bash
git add <已解决文件>
git rebase --continue
git push origin main
```

### SSH 无法连接

```bash
ssh -T git@github.com
ssh-add ~/.ssh/id_ed25519
git remote get-url origin
```

确认远端地址使用 `git@github.com:...`，并确认 GitHub 账号对仓库有写权限。

### 撤销尚未提交的文件改动

```bash
git restore <文件路径>
```

该命令会丢弃指定文件的未提交改动，使用前确认内容不需要保留。

### 撤销最近一次提交但保留文件改动

```bash
git reset --soft HEAD~1
```

不要对已推送到共享分支的提交随意执行强制重写；需要修正时优先创建新提交。

## 本项目建议

每次修改方案后先运行：

```bash
git status
git diff --check
```

确认内容正确后再提交。推送完成后检查：

```bash
git status --short --branch
git log -1 --oneline --decorate
```

目标状态应显示本地分支与 `origin/main` 同步。
