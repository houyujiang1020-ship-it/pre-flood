# 上游源码锁定

克隆时间：2026-08-23（Asia/Shanghai）

| 项目 | 仓库 | 分支 | Commit | License | 状态 |
|---|---|---|---|---|---|
| MapGIS-Desktop-Java | https://github.com/MapGIS/MapGIS-Desktop-Java | `master` | `cc7e9eef74b9e051ed074f98cfaefd25b8c69f96` | Apache License 2.0（仓库 `LICENSE`） | 已克隆 |
| SpaceNet8 | https://github.com/SpaceNetChallenge/SpaceNet8 | `main` | `30ca30c2530c6a234d040f60a99a7366ff62d756` | Apache License 2.0（仓库 `LICENSE`） | Git partial clone 取得 commit 后，由同 commit 的 GitHub 官方 codeload 归档恢复完整工作树 |

上游代码保存在 `upstream/`，主工程不直接魔改上游。SpaceNet8 因 GitHub partial-clone blob 下载异常采用官方源码归档作为只读快照，commit 由 GitHub API 与本地 partial clone 双重确认。
