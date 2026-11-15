// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <filesystem>

namespace veyra::ngx {
inline bool completeAnrRuntime(const std::filesystem::path& directory) {
    std::error_code error;
    for(const auto* name:{L"nvngx_dlssg.dll",L"nr_fg.ini",L"path_table.json",L"size_table.json",
            L"adapters/pack.nrx",L"kernels/pack.nrx",L"kernels-portable/pack.nrx",
            L"programs/fg-lite-any-portable-srgb8/pack.nrx",L"programs/fg-lite-any-portable-pq10/pack.nrx"})
        if(!std::filesystem::is_regular_file(directory/name,error))return false;
    return true;
}
// runtimeRoot is Veyra's runtime/experimental directory. Support both the
// existing provider-only installation and the author's untouched full ZIP.
// Never search for/load the archive's OptiScaler dxgi.dll or run its installer.
inline std::filesystem::path anrRuntimeDirectory(const std::filesystem::path& runtimeRoot) {
    const auto base=(runtimeRoot/"../anr").lexically_normal();
    if(completeAnrRuntime(base))return base;
    const auto full=base/"game/OptiScaler/custom/Apex Neural Rendering FG/dlssg";
    if(completeAnrRuntime(full))return full;
    return base;
}
}
