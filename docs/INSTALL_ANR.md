# Optional ANR runtime installation

Veyra does not include ANR binaries, models or program packs. Download them
directly from the ANR author if you want to use this optional backend.

1. Close Veyra.
2. Open the [official ANR releases page](https://github.com/apex-compute/ANR/releases)
   and download the latest **full ZIP package**.
3. Create `runtime\anr` beside `veyra_qml_ui.exe`.
4. Extract the ZIP's **contents** into `runtime\anr`, preserving its directory
   structure. Do not add an extra folder named after the ZIP.
5. Restart Veyra and select **Apex ANR · Beta** in the frame-generation options.

For the full package layout supported by this release, the provider is located at:

```text
Veyra/
  veyra_qml_ui.exe
  runtime/
    anr/
      game/
        OptiScaler/
          custom/
            Apex Neural Rendering FG/
              dlssg/
                nvngx_dlssg.dll
                nr_fg.ini
                adapters/
                kernels/
                kernels-portable/
                programs/
                ...
```

Veyra loads the ANR provider directly. Do not run the ZIP's installer or copy
`game\dxgi.dll` beside Veyra. Keep all provider files and subfolders together.
Existing installations with provider files directly under `runtime\anr` also
work and take precedence over a nested installation.

When upgrading, close Veyra, move the old runtime contents outside the application
folder, then extract the complete replacement package. Do not mix DLLs, models
or program packs from different releases. Future ANR releases depend on continued
compatibility with Veyra's provider interface and supported folder layouts.

---

## 可选 ANR 运行组件安装

Veyra 不附带 ANR 二进制文件、模型或程序包。如需使用此可选后端，请直接从 ANR 作者处下载。

1. 关闭 Veyra。
2. 打开 [ANR 官方发布页面](https://github.com/apex-compute/ANR/releases)，下载最新的**完整 ZIP 包**。
3. 在 `veyra_qml_ui.exe` 所在目录中创建 `runtime\anr` 文件夹。
4. 将 ZIP 内的**全部内容**解压到 `runtime\anr`，保留原始目录结构。不要额外套一层以压缩包命名的文件夹。
5. 重新启动 Veyra，在补帧选项中选择 **Apex ANR · Beta**。

本版本支持的完整包目录结构如上图所示，组件应位于：

```text
runtime\anr\game\OptiScaler\custom\Apex Neural Rendering FG\dlssg\nvngx_dlssg.dll
```

Veyra 直接加载 ANR 组件。无需运行压缩包内的安装程序，也不要将 `game\dxgi.dll`
复制到 Veyra 主程序旁。请保留完整的组件文件和子目录。直接放在 `runtime\anr`
下的旧式组件布局仍可使用，并且优先于嵌套安装目录。

升级时请先关闭 Veyra，将旧运行组件移到程序目录之外，再解压完整的新包。
不要混用不同版本的 DLL、模型或程序包。后续 ANR 版本能否使用，取决于其与
Veyra 组件接口及所支持目录结构的兼容性。
