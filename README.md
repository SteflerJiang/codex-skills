# Codex Skills

我日常使用、调整和整理的 Codex 技能合集。每个技能独立安装，并注明原始来源和本仓库的改动。

| 技能 | 用途 | 来源 |
| --- | --- | --- |
| [z-video-study](skills/z-video-study/) | 沿用原版视频下载/转录/学习网页流程，以本机Codex CLI替换第三方模型API | 基于 [tjxj/z-skills](https://github.com/tjxj/z-skills) 的 z-video-study-webpage-qwen 与 z-video-downloader |

这个版本的定位是：**保留原有视频工作流，专门适配本地安装的官方 Codex CLI，不再单独配置第三方模型。** 下载脚本沿用原版，未改为精简下载器。

完整执行说明见 [SKILL.md](skills/z-video-study/SKILL.md)，原版下载能力与命令见 [下载说明](skills/z-video-study/references/download.md)。

## 安装与使用

在 Codex 中输入：

```text
$skill-installer 从 https://github.com/SteflerJiang/codex-skills/tree/main/skills/z-video-study 安装技能
```

安装后，让 Codex 执行技能目录中的 `install.sh`，检查依赖，并在新会话中输入：

```text
$z-video-study 分析这个视频：https://视频链接
```

也可以分析本地视频：

```text
用 z-video-study 分析 /完整路径/video.mp4，生成图文学习网页。
```

### 手动安装

需要 Python 3.11+、FFmpeg（含 ffprobe）和支持图像与结构化输出的官方 Codex CLI。macOS / Linux 可运行脚本；Windows 建议使用 WSL。当前在 macOS、Python 3.12、Codex CLI 0.154.0 上验证。

```bash
git clone https://github.com/SteflerJiang/codex-skills.git
cd codex-skills
# 默认目录；若配置了 CODEX_HOME，使用其下的 skills 目录。
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/z-video-study "${CODEX_HOME:-$HOME/.codex}/skills/"
bash "${CODEX_HOME:-$HOME/.codex}/skills/z-video-study/install.sh"
codex login
bash "${CODEX_HOME:-$HOME/.codex}/skills/z-video-study/run.sh" doctor
```

已有同名技能时先自行备份并比较，不直接覆盖。`install.sh` 在技能目录中创建 `.venv`，优先使用已有的 `uv`，否则使用 Python venv/pip；不会读取邮箱设置或要求 Qwen/OpenAI API Key。

安装 FFmpeg、Python 和 Codex CLI 的示例：

```bash
# macOS，需已安装 Homebrew 与 npm
brew install python@3.12 ffmpeg
npm install -g @openai/codex
# Ubuntu / Debian：安装 Python 3.11+、python3-venv、ffmpeg，再安装 Codex CLI。
```

Whisper 首次使用会下载模型；默认 `base`，本地 CPU 也可运行。需要复用已有字幕时传入 `--transcript`，无需重新转录。

### 命令行

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/z-video-study"

# 视频链接：默认单视频、最高 1080p，下载后自动分析
bash "$SKILL_DIR/run.sh" --url "https://www.bilibili.com/video/BV..." --title "视频主题"

# 本地视频
bash "$SKILL_DIR/run.sh" --video "/完整路径/video.mp4" --out-dir "/完整路径/study"

# 复用带时间戳的转录；纯文本也支持，但时间定位是近似的
bash "$SKILL_DIR/run.sh" --video "/完整路径/video.mp4" --transcript "/完整路径/transcript.json"

# 平台要求登录时传入已有的 Netscape cookies 文件
bash "$SKILL_DIR/run.sh" --url "https://视频链接" --cookies-file "/完整路径/cookies.txt"

# 仅下载：原下载器的字幕、画质、批量、视频号和续传参数仍可使用
bash "$SKILL_DIR/run.sh" download --title "视频主题" --subtitles "https://视频链接"
bash "$SKILL_DIR/run.sh" download --run-dir "/完整路径/原下载目录" "https://视频链接"
```

已内置上游完整 `z-video-downloader` 脚本与测试，无需另外安装下载技能。默认输出 `Video/Downloads/YYYY-MM-DD-主题/`，包含 `download-report.md/json`。普通平台走yt-dlp，直链使用HTTP续传；还保留字幕、封面、画质、下载历史、批量清单和视频号等原有功能，详见[下载说明](skills/z-video-study/references/download.md)。

视频号沿用原版在线解析服务；YouTube无Cookie遇登录验证时沿用原版Invidious回退，可用 `download --no-invidious-fallback` 关闭。下载流程没有第三方模型API调用。自动 `--url` 流程读取下载报告后分析实际文件；高级下载参数使用 `download` 子命令，再把本地视频交给 `--video`。

## z-video-study 的工作方式

1. 原版 z-video-downloader 下载视频，或使用本地文件。
2. FFmpeg 抽取时间轴画面与音轨；Whisper 在本机转录，或复用已有转录。
3. 本机启动官方 `codex exec`，通过已有的 ChatGPT 登录进行多模态分析，逐批校验画面引用与分段覆盖。
4. 生成含知识卡片、时间线、本地播放器和复习问题的 HTML 网页。

不需要 Qwen/百炼 API。Codex 分析消耗相应套餐额度及适用积分，并非无限免费。下载和音频转录在本地；分析时，抽样截图和转录会提交给 Codex 服务，因此不是完全离线分析。程序不会提取或复制登录凭据，不会在失败时切换为 API Key 计费。

默认 12 张画面、每批 4 段，再做一次汇总。长视频或密集图表可调整 `--frame-count`（4–36）、`--max-segments`、`--codex-batch-size` 和 `--codex-timeout`。完整音轨在本地转录，但当前每段发送给模型的文字最多4000字符；长视频应增加分段或按章节分析。这是转录与画面抽样，不是逐帧连续理解；数字、专名和结论仍需对照原视频复核。

主要产物：`study-summary.html`、`analysis.json`、`segments.json`、`storyboard.json`、`transcript.txt/json`、`assets/`、`run-report.json`。本地缓存按输入内容保存；同目录重跑可复用有效批次。报告记录实际模型与调用，不固定某个模型名称。

## 来源与改造

感谢 **[tjxj](https://github.com/tjxj)** 的 **[z-skills](https://github.com/tjxj/z-skills)**。本技能是基于其 [z-video-study-webpage-qwen](https://github.com/tjxj/z-skills/tree/a29467ebf92b244aabc1edc19bd11028fb9a3bb0/z-video-study-webpage-qwen) 的修改版本，并非从零原创，也不是上游官方版本。

沿用了原技能的视频预处理、学习网页模板及部分测试，并内置上游完整视频下载实现；本仓库把 Qwen HTTP 分析改为官方 Codex CLI，加入分批图像分析、严格画面引用校验、缓存恢复、凭据隔离，并移除原来的 Qwen 配置入口。相对路径启动器、依赖安装/检查及URL入口只负责环境适配和衔接，不重写原有下载策略。

具体来源、提交版本、文件对应关系和许可状态见每个技能内的 [来源说明](skills/z-video-study/references/source.md)。上游该技能在参考版本中没有附带明确的适用许可证；本仓库不会据此擅自将上游代码重新授权为 MIT，具体使用和再分发权限应以上游授权为准。

## 验证

```bash
PYTHON=python3.12  # 或其他 Python 3.11+
"$PYTHON" -m unittest discover -s skills/z-video-study/tests
bash skills/z-video-study/run.sh doctor
```

自动测试不调用真实模型。可用 `--mock-analysis --skip-transcribe` 检查抽帧和网页模板；这种结果会在报告中标记为 `mock`，不代表真实内容分析。安装过程需要网络，真实分析需要 Codex 登录和额度。
