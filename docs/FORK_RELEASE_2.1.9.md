# Veyra 2.1.9

This is the CallMeSlinky fork, based on upstream Veyra 2.1.9. Credit to
[Likely7 and the upstream contributors](https://github.com/Likely7/Veyra-NRVideo)
for the original application and upstream features.

## English

### Added and fixed in this fork

- **AV1 encoding** for recording, instant replay and video export, with H.264,
  H.265 / HEVC and AV1 selectors. Existing HEVC settings remain compatible.
  AV1 encoding requires a supported NVIDIA NVENC device; unsupported requests
  fail explicitly instead of silently changing codecs. Includes SDR and 10-bit
  HDR encoding, queued exports and MP4/Matroska output.
- **Screenshot and recording controls in the top dropdown dock**, with recording
  status and a saving indicator, available without switching to the Pro page.
- **Badge and dialog sizing fixes** so long translated messages wrap within
  their cards instead of overflowing.
- **Replay pause/resume fixes** so paused wall time does not consume the replay
  buffer or introduce gaps in saved clips. Paused replay remains saveable.
- **Independent ANR integration**, with corrected pixel-space motion handling
  and compatibility with earlier custom ANR presets and session files.
- **Optional user-installed ANR runtimes**, supporting provider files directly
  inside `runtime/anr` and the official full ZIP's nested directory layout.
  No ANR binaries, models, configuration or program packs are bundled.

Retains upstream 2.1.9 features, including dusk appearance, editable exclusion
outlines, capture audio fixes, virtual desktop capture, G-SYNC profile controls
and AMD frame-generation updates. These are upstream contributions, not new
features authored by this fork.

### Download and install

Download `Veyra-2.1.9-win64-portable.zip`, extract the entire archive to a new
writable folder, then run `Start Veyra.cmd`. The application is named
**Veyra 2.1.9**. Settings for this release use its own local profile.

For optional ANR, download the latest **full ZIP package** from the
[official ANR releases page](https://github.com/apex-compute/ANR/releases), close
Veyra and extract the ZIP's contents into `runtime/anr` beside the executable.
Preserve all directories, restart Veyra and select **Apex ANR · Beta**.
Do not run the archive's installer or copy `game/dxgi.dll` beside Veyra.
Replace complete runtime contents when upgrading; do not mix versions.
Future ANR releases require a compatible provider interface and folder layout.
See [full English and Simplified Chinese installation instructions](INSTALL_ANR.md).

### Validation and limitations

The custom integration passed 209 Qt Quick tests with no failures/errors and
one skip, 53 replay checks, 48 ANR settings/migration checks, 683 FG settings
checks, 62 VRR policy assertions, and independent decoding of 18 SDR/HDR codec
outputs. The tested external ANR runtime passed 133 GPU checks and SDR/HDR mask
composition checks. These checks used this development PC and synthetic media;
they do not establish performance or compatibility on every system.

- A known simultaneous HEVC HDR recording/replay device-removal failure remains
  unresolved. HDR recording and replay were validated separately.
- AV1 encoding on AMD/Intel is not implemented. Their existing H.264/HEVC paths
  remain available. AMD FRC support is compiled in but was not tested on AMD
  hardware here; its runtime comes from the user's AMD graphics driver.
- Physical capture cards, physical HDR display output and long-duration
  stability were not validated here. Optional PS5/Moonlight/Xbox and libass
  backends are not enabled in this binary's existing dependency configuration.
- The upstream startup music asset is not bundled; the startup music feature
  remains optional.

The release includes the matching application source and SHA256 checksums.
See [fork build and dependency information](FORK_BUILD_2.1.9.md).

---

## 简体中文

这是基于上游 Veyra 2.1.9 的 CallMeSlinky 分支。感谢
[Likely7 及上游贡献者](https://github.com/Likely7/Veyra-NRVideo)
开发原始应用并提供上游功能。

### 本分支新增与修复

- **新增 AV1 编码**，支持录制、即时回放和视频导出，并提供 H.264、H.265 / HEVC
  和 AV1 选择。保留原有 HEVC 设置兼容性。AV1 编码需要受支持的 NVIDIA NVENC
  设备；不受支持时明确报错，不会静默切换编码。包含 SDR、10 位 HDR 编码、
  队列导出以及 MP4／Matroska 输出。
- **顶部下拉工具栏新增截图和录制入口**，包含录制状态与保存中提示，无需切换到专业页面。
- **修复徽标和对话框尺寸问题**，较长的翻译文本可在卡片内自动换行，避免溢出。
- **修复即时回放暂停与恢复行为**，暂停时间不再占用回放缓冲，也不会在保存的视频中
  产生时间间隙。暂停期间仍可保存已有回放。
- **独立 ANR 接入实现**，包含像素空间运动处理修正，以及早期自定义 ANR 预设和会话文件兼容。
- **支持用户自行安装 ANR 运行组件**，兼容直接放入 `runtime/anr` 的组件文件，
  以及官方完整 ZIP 的原始嵌套目录结构。不附带 ANR 二进制文件、模型、配置或程序包。

同时保留上游 2.1.9 的日落主题、可编辑剔除区域、采集音频修复、虚拟桌面采集、
G-SYNC 设置和 AMD 补帧更新。这些属于上游贡献，并非本分支独立新增的功能。

### 下载与安装

下载 `Veyra-2.1.9-win64-portable.zip`，完整解压到一个新的可写目录，运行
`Start Veyra.cmd`。程序名称为 **Veyra 2.1.9**，本次发行使用独立的本地配置目录。

如需使用 ANR，请从 [ANR 官方发布页面](https://github.com/apex-compute/ANR/releases)
下载最新的**完整 ZIP 包**。关闭 Veyra，将 ZIP 内的全部内容解压到主程序旁的
`runtime/anr`，保留原始目录结构。重新启动 Veyra，选择 **Apex ANR · Beta**。
无需运行压缩包内的安装程序，也不要将 `game/dxgi.dll` 复制到 Veyra 主程序旁。
升级时请完整替换运行组件，避免混用不同版本。后续 ANR 版本能否使用，取决于其
组件接口和目录结构的兼容性。详见 [中英文安装说明](INSTALL_ANR.md)。

### 验证与限制

自定义整合已通过 209 项 Qt Quick 测试（无失败或错误，跳过 1 项）、53 项回放检查、
48 项 ANR 设置／迁移检查、683 项补帧设置检查、62 项 VRR 策略断言，以及 18 个
SDR／HDR 编码输出的独立解码。受测外部 ANR 组件通过 133 项 GPU 检查和 SDR／HDR
剔除区域合成检查。测试使用本机和合成素材，不代表所有设备上的性能或兼容性。

- 同时进行 HEVC HDR 录制与即时回放时，仍存在尚未解决的设备移除问题。
  HDR 录制和回放已分别验证。
- 尚未实现 AMD／Intel AV1 编码；其原有 H.264／HEVC 路径仍可使用。
  已编译 AMD FRC 支持，但本机尚未完成 AMD 实卡验证；其运行库由用户的 AMD 显卡驱动提供。
- 本机未验证真实采集卡、物理 HDR 显示输出或长时间稳定性。本包现有依赖配置
  未启用可选的 PS5／Moonlight／Xbox 和 libass 后端。
- 不附带上游启动音乐素材；启动音乐功能仍为可选。

本次发行提供对应应用源码和 SHA256 校验文件。
详见 [本分支构建与依赖说明](FORK_BUILD_2.1.9.md)。
