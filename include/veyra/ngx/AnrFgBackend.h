// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "veyra/ngx/DlssFgBackend.h"
#include <memory>
#include <string>

namespace veyra::ngx {
// Hosts the ANR provider's NGX-compatible exports directly, independently of
// NVIDIA's NGX core. The original provider and its model packs stay external.
class AnrFgBackend {
public:
    AnrFgBackend();
    ~AnrFgBackend();
    AnrFgBackend(const AnrFgBackend&) = delete;
    AnrFgBackend& operator=(const AnrFgBackend&) = delete;
    static std::wstring runtimeDirectory(const std::wstring& runtimeRoot);
    static bool runtimeAvailable(const std::wstring& runtimeRoot);
    bool initialize(ID3D12Device*, ID3D12GraphicsCommandList*, const std::wstring& runtimeRoot,
                    unsigned width, unsigned height, DXGI_FORMAT, unsigned multiplier);
    // Motion resource is current->previous in working-resolution pixels.
    // DLSS's normalized reverse-scale fields in EvalDesc do not apply to ANR.
    bool evaluate(ID3D12GraphicsCommandList*, const DlssFgBackend::EvalDesc&);
    bool created() const;
    unsigned maxGenerated() const;
    bool shutdown(); // Caller drains its command queue before releasing features.
private:
    struct Impl;
    std::unique_ptr<Impl> p_;
};
}
