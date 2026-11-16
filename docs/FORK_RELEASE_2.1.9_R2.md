# Veyra 2.1.9 — capture settings update

Custom Resolution now has an **Enter a custom resolution** checkbox. The input
and **Check and select** button are greyed out until editing is enabled.
Enabling editing copies the selected resolution into the input; 1920x1080 is
only an example placeholder. Typing or unchecking does not change the selected
capture resolution. Click **Check and select** to apply a driver-supported size.
The checkbox and apply action also support keyboard operation.

Download **Veyra-2.1.9-win64-portable.zip**, extract the complete ZIP into a
writable folder, and run **Start Veyra.cmd**. Settings are stored in this copy's
`user-data` folder. The application version remains **2.1.9**; the release tag
`v2.1.9-slinky-r2` identifies this update.

Validation: Release build, compiled translation checks, device-free custom
resolution interaction checks, English/Chinese layout inspection, and the Qt
Quick regression suite (208 passed, 0 failed, 1 skipped). The assembled portable
passed the English capture-dialog check and isolated startup with a minimal
PATH. ZIP CRCs and all payload hashes were verified. Physical capture hardware
was not exercised for this UI change.

Product/source commit: `b4407610812dc60d3df908a36abf5108d3b7ebb2`.
The corresponding source ZIP and SHA256SUMS are included with this release.

The existing custom features and installation instructions are described in the
[previous 2.1.9 release](https://github.com/CallMeSlinky/Veyra-NRVideo/releases/tag/v2.1.9-slinky).
Optional ANR is installed separately; see the
[ANR installation guide](https://github.com/CallMeSlinky/Veyra-NRVideo/blob/main/docs/INSTALL_ANR.md).
No ANR runtime or startup music is bundled.

## 简体中文

自定义分辨率新增「手动输入分辨率」复选框。未勾选时，输入框和「检查并选择」
按钮显示为灰色且不可操作。勾选后，输入框会填入当前选中的分辨率；1920x1080
仅作为示例占位文字。输入或取消勾选不会改变当前采集分辨率；点击「检查并选择」
后，才会应用采集卡驱动支持的尺寸。复选框和应用按钮支持键盘操作。

下载 **Veyra-2.1.9-win64-portable.zip**，完整解压到可写目录后运行
**Start Veyra.cmd**。设置保存在本副本的 `user-data` 目录中。程序版本仍为
**2.1.9**，本次更新的发行标签为 `v2.1.9-slinky-r2`。

Release 构建、翻译检查、自定义分辨率交互及中英文布局检查通过；Qt Quick
回归结果为 208 通过、0 失败、1 跳过。便携包的英文采集对话框、最小 PATH
独立启动、ZIP CRC 和全部文件哈希均已验证。本次界面修改未进行实体采集卡测试。

对应源码提交为 `b4407610812dc60d3df908a36abf5108d3b7ebb2`；发行资产包含
对应源码 ZIP 和 SHA256SUMS。原有功能见上方旧版更新说明；可选 ANR 需自行安装，
本包不包含 ANR 运行组件或启动音乐。
