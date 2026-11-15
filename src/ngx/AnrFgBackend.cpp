// SPDX-License-Identifier: GPL-3.0-only
#include "veyra/ngx/AnrFgBackend.h"
#include "veyra/ngx/AnrRuntimeLayout.h"
#include "veyra/Log.h"
#include <Windows.h>
#include <nvsdk_ngx_defs_dlssg.h>
#include <algorithm>
#include <filesystem>
#include <format>
#include <unordered_map>
#include <variant>

namespace veyra::ngx {
namespace {
// Implement the SDK's public parameter ABI locally: ANR must also work when
// the NVIDIA driver/core is absent. Preserve 64-bit frame IDs exactly.
class Parameters final : public NVSDK_NGX_Parameter {
    using Value = std::variant<unsigned long long, double, long long, void*>;
    std::unordered_map<std::string, Value> values_;
    template<class T> NVSDK_NGX_Result number(const char* name,T* out) const {
        const auto it=values_.find(name);
        if(!out||it==values_.end()||std::holds_alternative<void*>(it->second))return NVSDK_NGX_Result_FAIL_InvalidParameter;
        std::visit([&](auto v){if constexpr(!std::is_pointer_v<decltype(v)>)*out=static_cast<T>(v);},it->second);
        return NVSDK_NGX_Result_Success;
    }
    template<class T> NVSDK_NGX_Result pointer(const char* name,T** out) const {
        const auto it=values_.find(name);
        if(!out||it==values_.end()||!std::holds_alternative<void*>(it->second))return NVSDK_NGX_Result_FAIL_InvalidParameter;
        *out=static_cast<T*>(std::get<void*>(it->second));return NVSDK_NGX_Result_Success;
    }
public:
    void Set(const char* n,unsigned long long v) override {values_[n]=v;}
    void Set(const char* n,float v) override {values_[n]=double(v);}
    void Set(const char* n,double v) override {values_[n]=v;}
    void Set(const char* n,unsigned v) override {values_[n]=static_cast<unsigned long long>(v);}
    void Set(const char* n,int v) override {values_[n]=static_cast<long long>(v);}
    void Set(const char* n,ID3D11Resource* v) override {values_[n]=static_cast<void*>(v);}
    void Set(const char* n,ID3D12Resource* v) override {values_[n]=static_cast<void*>(v);}
    void Set(const char* n,void* v) override {values_[n]=v;}
    NVSDK_NGX_Result Get(const char* n,unsigned long long* v) const override {return number(n,v);}
    NVSDK_NGX_Result Get(const char* n,float* v) const override {return number(n,v);}
    NVSDK_NGX_Result Get(const char* n,double* v) const override {return number(n,v);}
    NVSDK_NGX_Result Get(const char* n,unsigned* v) const override {return number(n,v);}
    NVSDK_NGX_Result Get(const char* n,int* v) const override {return number(n,v);}
    NVSDK_NGX_Result Get(const char* n,ID3D11Resource** v) const override {return pointer(n,v);}
    NVSDK_NGX_Result Get(const char* n,ID3D12Resource** v) const override {return pointer(n,v);}
    NVSDK_NGX_Result Get(const char* n,void** v) const override {return pointer(n,v);}
    void Reset() override {values_.clear();}
};
// Keep SEH at the DLL boundary and poison a failed session. Do not retry a
// provider handle after an exception; the graph owns GPU draining/recovery.
template<class F,class... A> NVSDK_NGX_Result invoke(F fn,A... args) {
    __try {return fn(args...);}
    __except(EXCEPTION_EXECUTE_HANDLER) {return NVSDK_NGX_Result_FAIL_PlatformError;}
}
bool result(NVSDK_NGX_Result r,const char* operation) {
    if(NVSDK_NGX_SUCCEED(r))return true;
    log::error("anr",std::format("{} result=0x{:08X}",operation,unsigned(r)));return false;
}
}
struct AnrFgBackend::Impl {
    HMODULE module=nullptr;
    ID3D12Device* device=nullptr;
    NVSDK_NGX_Handle* handle=nullptr;
    Parameters params;
    bool initialized=false,fatal=false;
    unsigned width=0,height=0,maxGenerated=0;
    float projection[16]{},inverse[16]{},identity[16]{};
    using Init=NVSDK_NGX_Result(NVSDK_CONV*)(unsigned long long,const wchar_t*,ID3D12Device*,NVSDK_NGX_Version,const NVSDK_NGX_FeatureCommonInfo*);
    using Populate=NVSDK_NGX_Result(NVSDK_CONV*)(NVSDK_NGX_Parameter*);
    using Create=NVSDK_NGX_Result(NVSDK_CONV*)(ID3D12GraphicsCommandList*,NVSDK_NGX_Feature,NVSDK_NGX_Parameter*,NVSDK_NGX_Handle**);
    using Evaluate=NVSDK_NGX_Result(NVSDK_CONV*)(ID3D12GraphicsCommandList*,const NVSDK_NGX_Handle*,NVSDK_NGX_Parameter*,PFN_NVSDK_NGX_ProgressCallback);
    using Release=NVSDK_NGX_Result(NVSDK_CONV*)(NVSDK_NGX_Handle*);
    using Shutdown=NVSDK_NGX_Result(NVSDK_CONV*)(ID3D12Device*);
    Init init=nullptr;Populate populate=nullptr;Create create=nullptr;Evaluate evaluate=nullptr;Release release=nullptr;Shutdown shutdown=nullptr;
};
AnrFgBackend::AnrFgBackend():p_(std::make_unique<Impl>()){}
AnrFgBackend::~AnrFgBackend(){shutdown();}
std::wstring AnrFgBackend::runtimeDirectory(const std::wstring& root) {
    return anrRuntimeDirectory(root).wstring();
}
bool AnrFgBackend::runtimeAvailable(const std::wstring& root) {
    return completeAnrRuntime(runtimeDirectory(root));
}
bool AnrFgBackend::initialize(ID3D12Device* device,ID3D12GraphicsCommandList* list,const std::wstring& root,
                             unsigned width,unsigned height,DXGI_FORMAT format,unsigned multiplier) {
    if(!device||!list||!width||!height||multiplier<2||multiplier>6||
       (format!=DXGI_FORMAT_R8G8B8A8_UNORM&&format!=DXGI_FORMAT_R10G10B10A2_UNORM)||!runtimeAvailable(root))return false;
    auto& p=*p_;
    if(p.module)return false;
    const auto dir=std::filesystem::absolute(runtimeDirectory(root));
    const auto file=dir/L"nvngx_dlssg.dll";
    p.module=LoadLibraryExW(file.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!p.module){log::error("anr",std::format("LoadLibrary win32={}",GetLastError()));return false;}
#define ANR_BIND(member,type,name) p.member=reinterpret_cast<Impl::type>(GetProcAddress(p.module,name));if(!p.member){log::error("anr","Missing export " name);return false;}
    ANR_BIND(init,Init,"NVSDK_NGX_D3D12_Init_Ext")
    ANR_BIND(populate,Populate,"NVSDK_NGX_D3D12_PopulateParameters_Impl")
    ANR_BIND(create,Create,"NVSDK_NGX_D3D12_CreateFeature")
    ANR_BIND(evaluate,Evaluate,"NVSDK_NGX_D3D12_EvaluateFeature")
    ANR_BIND(release,Release,"NVSDK_NGX_D3D12_ReleaseFeature")
    ANR_BIND(shutdown,Shutdown,"NVSDK_NGX_D3D12_Shutdown1")
#undef ANR_BIND
    p.device=device;p.width=width;p.height=height;
    if(!result(invoke(p.init,1ull,dir.c_str(),device,NVSDK_NGX_Version_API,static_cast<const NVSDK_NGX_FeatureCommonInfo*>(nullptr)),"Init_Ext"))return false;
    p.initialized=true;
    if(!result(invoke(p.populate,static_cast<NVSDK_NGX_Parameter*>(&p.params)),"PopulateParameters"))return false;
    p.params.Get(NVSDK_NGX_DLSSG_Parameter_MultiFrameCountMax,&p.maxGenerated);
    p.maxGenerated=std::min(p.maxGenerated,5u);
    if(multiplier-1>p.maxGenerated){log::error("anr",std::format("Requested {}X exceeds provider maximum {}X",multiplier,p.maxGenerated+1));return false;}
    auto& a=p.params;
    const float aspect=float(width)/float(height),nearPlane=0.1f,farPlane=1000.0f;
    const float z=farPlane/(farPlane-nearPlane),offset=-nearPlane*z;
    for(unsigned i=0;i<4;++i)p.identity[i*5]=1.0f;
    p.projection[0]=1.0f/aspect;p.projection[5]=1.0f;p.projection[10]=z;p.projection[11]=1.0f;p.projection[14]=offset;
    p.inverse[0]=aspect;p.inverse[5]=1.0f;p.inverse[11]=1.0f/offset;p.inverse[14]=1.0f;p.inverse[15]=-z/offset;
    a.Set(NVSDK_NGX_DLSSG_Parameter_CameraViewToClip,static_cast<void*>(p.projection));
    a.Set(NVSDK_NGX_DLSSG_Parameter_ClipToCameraView,static_cast<void*>(p.inverse));
    a.Set(NVSDK_NGX_DLSSG_Parameter_ClipToLensClip,static_cast<void*>(p.identity));
    a.Set(NVSDK_NGX_DLSSG_Parameter_ClipToPrevClip,static_cast<void*>(p.identity));
    a.Set(NVSDK_NGX_DLSSG_Parameter_PrevClipToClip,static_cast<void*>(p.identity));
    a.Set(NVSDK_NGX_DLSSG_Parameter_CameraNear,nearPlane);a.Set(NVSDK_NGX_DLSSG_Parameter_CameraFar,farPlane);
    a.Set(NVSDK_NGX_DLSSG_Parameter_CameraFOV,1.5707963f);a.Set(NVSDK_NGX_DLSSG_Parameter_CameraAspectRatio,aspect);
    a.Set(NVSDK_NGX_DLSSG_Parameter_CameraUpY,1.0f);a.Set(NVSDK_NGX_DLSSG_Parameter_CameraRightX,1.0f);a.Set(NVSDK_NGX_DLSSG_Parameter_CameraFwdZ,1.0f);
    a.Set(NVSDK_NGX_DLSSG_Parameter_CameraMotionIncluded,1u);
    a.Set(NVSDK_NGX_Parameter_CreationNodeMask,1u);a.Set(NVSDK_NGX_Parameter_VisibilityNodeMask,1u);
    a.Set(NVSDK_NGX_Parameter_Width,width);a.Set(NVSDK_NGX_Parameter_Height,height);
    a.Set(NVSDK_NGX_DLSSG_Parameter_Width,width);a.Set(NVSDK_NGX_DLSSG_Parameter_Height,height);
    a.Set(NVSDK_NGX_DLSSG_Parameter_InternalWidth,width);a.Set(NVSDK_NGX_DLSSG_Parameter_InternalHeight,height);
    a.Set(NVSDK_NGX_DLSSG_Parameter_BackbufferFormat,unsigned(format));
    a.Set(NVSDK_NGX_DLSSG_Parameter_DynamicResolution,0u);
    if(!result(invoke(p.create,list,NVSDK_NGX_Feature_FrameGeneration,static_cast<NVSDK_NGX_Parameter*>(&a),&p.handle),"CreateFeature")||!p.handle)return false;
    log::info("anr",std::format("Created {}x{} format={} multiplier={} maxGenerated={} (direct external provider)",width,height,unsigned(format),multiplier,p.maxGenerated));
    return true;
}
bool AnrFgBackend::evaluate(ID3D12GraphicsCommandList* list,const DlssFgBackend::EvalDesc& d) {
    auto& p=*p_;auto& a=p.params;
    if(!created()||!list||!d.backbuffer||!d.outputInterpolated||d.multiFrameCount<1||d.multiFrameCount>p.maxGenerated||d.multiFrameIndex<1||d.multiFrameIndex>d.multiFrameCount)return false;
    a.Set(NVSDK_NGX_DLSSG_Parameter_Backbuffer,d.backbuffer);
    a.Set(NVSDK_NGX_DLSSG_Parameter_Depth,d.depth);a.Set(NVSDK_NGX_DLSSG_Parameter_MVecs,d.mvecs);
    a.Set(NVSDK_NGX_DLSSG_Parameter_OutputInterpolated,d.outputInterpolated);
    a.Set(NVSDK_NGX_DLSSG_Parameter_OutputDisableInterpolation,d.outputDisableInterpolation);
    a.Set(NVSDK_NGX_DLSSG_Parameter_OutputReal,static_cast<ID3D12Resource*>(nullptr));
    a.Set(NVSDK_NGX_DLSSG_Parameter_HUDLess,static_cast<ID3D12Resource*>(nullptr));
    a.Set(NVSDK_NGX_DLSSG_Parameter_UI,static_cast<ID3D12Resource*>(nullptr));
    a.Set(NVSDK_NGX_DLSSG_Parameter_Reset,unsigned(d.reset));
    a.Set(NVSDK_NGX_DLSSG_Parameter_ColorBuffersHDR,unsigned(d.hdr));
    a.Set(NVSDK_NGX_DLSSG_Parameter_MultiFrameCount,d.multiFrameCount);
    a.Set(NVSDK_NGX_DLSSG_Parameter_MultiFrameIndex,d.multiFrameIndex);
    a.Set(NVSDK_NGX_DLSSG_Parameter_BackbufferFrameID,static_cast<unsigned long long>(d.frameId));
    // The direct ANR provider consumes current->previous PIXEL vectors.
    // The NGX-core DLSS adapter instead uses reversed, normalized scales.
    // Applying that DLSS conversion here nearly erases video motion. Verified
    // with known intermediate object positions, not just differing pixels.
    const bool legacyScale=GetEnvironmentVariableW(L"VEYRA_TEST_ANR_LEGACY_MOTION_SCALE",nullptr,0)>0;
    a.Set(NVSDK_NGX_DLSSG_Parameter_MvecScaleX,legacyScale?d.mvecScaleX:1.0f);
    a.Set(NVSDK_NGX_DLSSG_Parameter_MvecScaleY,legacyScale?d.mvecScaleY:1.0f);
    a.Set(NVSDK_NGX_DLSSG_Parameter_InputBackbufferSubrectWidth,p.width);a.Set(NVSDK_NGX_DLSSG_Parameter_InputBackbufferSubrectHeight,p.height);
    // ANR V.B14 reads these original NGX names (the 310.7 helpers use the
    // newer InputBackbuffer spellings); provide both aliases explicitly.
    a.Set("DLSSG.BackbufferSubrectWidth",p.width);a.Set("DLSSG.BackbufferSubrectHeight",p.height);
    a.Set(NVSDK_NGX_DLSSG_Parameter_MVecsSubrectWidth,p.width);a.Set(NVSDK_NGX_DLSSG_Parameter_MVecsSubrectHeight,p.height);
    a.Set(NVSDK_NGX_DLSSG_Parameter_DepthSubrectWidth,p.width);a.Set(NVSDK_NGX_DLSSG_Parameter_DepthSubrectHeight,p.height);
    const auto r=invoke(p.evaluate,list,static_cast<const NVSDK_NGX_Handle*>(p.handle),static_cast<NVSDK_NGX_Parameter*>(&a),static_cast<PFN_NVSDK_NGX_ProgressCallback>(nullptr));
    if(!result(r,"EvaluateFeature")){p.fatal=true;return false;}
    return true;
}
bool AnrFgBackend::created() const {return p_->handle&&!p_->fatal;}
unsigned AnrFgBackend::maxGenerated() const {return p_->maxGenerated;}
bool AnrFgBackend::shutdown() {
    auto& p=*p_;bool ok=true;
    if(p.handle&&p.release)ok=result(invoke(p.release,p.handle),"ReleaseFeature");
    p.handle=nullptr;
    if(p.initialized&&p.shutdown)ok=result(invoke(p.shutdown,p.device),"Shutdown1")&&ok;
    p.initialized=false;
    // A failed provider teardown may retain callbacks: keep that module mapped.
    if(p.module&&ok)FreeLibrary(p.module);
    p.module=nullptr;return ok;
}
}
