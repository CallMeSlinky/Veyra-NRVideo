# Veyra 2.1.9 fork build and corresponding source

Repository: https://github.com/CallMeSlinky/Veyra-NRVideo

The fork release is named **Veyra 2.1.9**. Its version resource is 2.1.9.0 and
its display version is 2.1.9. The release manifest records the exact source
commit and executable SHA256. `Veyra-2.1.9-source.zip` is generated from that
commit, excluding dependencies, local editor files, credentials, user profiles,
ANR assets and music. No official upstream binary is relabelled as this fork.

Build with MSVC 2022 x64/C++20, CMake/Ninja Release and Qt 6.8.3. This machine's
reproducible entry is `scripts/acceptance/build-apex-anr.py --label 2.1.9`.
The helper uses the existing E: dependencies and at most two build jobs. On
another machine, configure the matching dependency roots through CMake; see
[DEVELOPMENT.md](DEVELOPMENT.md) for the project's general build information.

Fixed dependency references and corresponding source links are retained in
the upstream [BUILD_2.1.9.md](BUILD_2.1.9.md), which describes upstream's own
build identities. Those hashes and upstream performance results are not the
fork binary's identities or this machine's measurements. In particular, retain
the matching patched FFmpeg source/build with slices256, dav1d, zlib and the
deinterlace module, rather than substituting an unpatched distribution.

This build uses nv-codec-headers 13.0.19.0, the existing patched FFmpeg 9.0.1
prefix, DLSS 310.7.0, Optical Flow SDK 5.0.7 and the configured FidelityFX/XeSS
dependencies. AMF SDK v1.5.3 public headers are MIT-licensed, pinned at
`57ee0cfb0e1a08d9041f77435653794c1b012be0`; use `VEYRA_AMF_SDK_ROOT` for its
`amf/public` directory. The AMD driver provides the AMF runtime; it is not
bundled. Preserve all notices and licenses from the runtime donor.

ANR provider DLLs, models, configuration and program packs are not included in
the release or source. Users obtain the optional runtime directly from its
author using [INSTALL_ANR.md](INSTALL_ANR.md). There is no automatic download,
mirror or installer execution. The independently written host adapter is part
of Veyra source. The upstream startup music asset is also not included.

## 简体中文

本分支发行名称为 **Veyra 2.1.9**，文件版本为 2.1.9.0，显示版本为 2.1.9。
发行清单记录确切的源码提交和 EXE SHA256。对应源码 ZIP 从该提交生成，不包含
依赖、编辑器本地文件、凭据、用户配置、ANR 资源或音乐。

构建使用 MSVC 2022 x64／C++20、CMake／Ninja Release 和 Qt 6.8.3。
请保留与运行库对应的 patched FFmpeg 源码、补丁、构建记录和许可。
上游 BUILD_2.1.9.md 中的二进制摘要和历史性能结果属于上游发行，不是本分支结果。
AMF 头文件仅用于构建，运行库由用户 AMD 驱动提供。ANR 运行组件由用户自行向作者
获取，不随本分支发行，也不自动下载；安装步骤见 INSTALL_ANR.md。
