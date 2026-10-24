# 来源、改造与许可状态

## 原始来源

- 原作者 / 仓库维护者：[tjxj](https://github.com/tjxj)
- 原仓库：[tjxj/z-skills](https://github.com/tjxj/z-skills)
- 原技能：[z-video-study-webpage-qwen](https://github.com/tjxj/z-skills/tree/a29467ebf92b244aabc1edc19bd11028fb9a3bb0/z-video-study-webpage-qwen)
- 原下载技能：[z-video-downloader](https://github.com/tjxj/z-skills/tree/a29467ebf92b244aabc1edc19bd11028fb9a3bb0/z-video-downloader)
- 参考提交：`a29467ebf92b244aabc1edc19bd11028fb9a3bb0`
- 本地改造与整理：2026-10-24，由 [SteflerJiang](https://github.com/SteflerJiang) 使用 Codex 协助完成。

本技能是上游技能的修改版本，不是从零原创，也不代表上游作者或 OpenAI 官方。保留 `z-` 名称前缀以便识别其来源。

## 文件与能力对应

| 当前文件 / 能力 | 来源或改动 |
| --- | --- |
| `scripts/video_study.py` | 改造自上游 `scripts/qwen_video_study.py`；沿用FFmpeg预处理、转录处理、HTML学习页面模板及媒体检查，移除Qwen HTTP调用，改接Codex CLI |
| `tests/test_video_study.py` | 改造自上游 `tests/test_qwen_video_study.py` |
| `scripts/codex_backend.py` | 本次改造新增；官方CLI、ChatGPT认证、分批多模态分析、JSON Schema、画面绑定、缓存恢复与凭据隔离 |
| `tests/test_codex_backend.py` | 本次改造新增；验证分段、缓存、认证与隔离等行为 |
| `scripts/download_video.py` | 保留上游完整下载实现；仅将作者写死的yt-dlp备用路径和子进程PATH改为当前Python环境的路径，平台策略保持原样 |
| `tests/test_download_video.py` | 原样保留上游下载测试 |
| `references/download.md` | 基于上游下载技能说明，替换本机路径和调用入口，保留实际下载流程、能力和平台策略 |
| `install.sh`、`run.sh`、`scripts/cli.py`、`scripts/doctor.py`、`tests/test_cli.py` | 为分享安装而新增；相对路径入口、独立环境、依赖检查及原下载报告到分析的衔接；URL入口不再另写下载实现 |

主要改动是把原先依赖Qwen/百炼API Key的视频分析改成调用本地安装的官方Codex CLI，复用ChatGPT登录；下载、抽帧和Whisper转录在本机，截图和转录通过Codex服务分析。没有Qwen SDK/API配置或失败自动切换服务的入口。

Codex CLI 的非交互、图像输入和结构化输出能力参考 [OpenAI官方文档](https://learn.chatgpt.com/docs/non-interactive-mode)；技能调用参考 [Skills & Plugins](https://learn.chatgpt.com/docs/skills-and-plugins)。第三方工具各自的许可不因本仓库发生变化。

## 许可说明

检查参考提交时，原仓库根目录和原视频技能目录均未附带适用于本技能的明确许可证文件。其他技能目录的许可证不能推定适用于本技能。

因此本仓库保留来源和权利归属说明，不将改编自上游的代码擅自重新授权为MIT或其他开源许可证，也不声称归因本身替代了上游许可。上游代码的使用和再分发权限以原作者明确授权为准；如需将此修改版用于再分发或商业用途，请先确认相应授权。后续取得明确授权时再同步更新许可说明。
