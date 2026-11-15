#pragma once
// AV1 NVENC compatibility transport. Native D3D11 owns the shared NV12/P010
// textures; a bounded D3D12 copy ring feeds them. All dependencies are GPU waits.
// Callers retain each source slot until its encoded output has been consumed.
#include <d3d11_4.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <vector>
#include <string>
#include <format>

namespace veyra::sink {
class NvencD3D11Bridge {
    template<class T> using Ptr=Microsoft::WRL::ComPtr<T>;
    struct Slot {
        Ptr<ID3D12Resource> source,shared;
        Ptr<ID3D11Texture2D> texture;
        Ptr<ID3D12CommandAllocator> allocator;
        Ptr<ID3D12GraphicsCommandList> list;
    };
    Ptr<ID3D11Device> device_;
    Ptr<ID3D11DeviceContext4> context_;
    Ptr<ID3D12CommandQueue> queue_;
    Ptr<ID3D11Fence> fence11_;
    Ptr<ID3D12Fence> fence12_;
    std::vector<Slot> slots_;
    uint64_t serial_=0;
    std::wstring error_;
    bool check(HRESULT hr,const wchar_t* op){
        if(SUCCEEDED(hr))return true;
        error_=std::format(L"AV1 D3D11 compatibility: {} failed (0x{:08X})",op,unsigned(hr));return false;
    }
public:
    ~NvencD3D11Bridge(){
        if(fence12_&&fence12_->GetCompletedValue()<serial_){
            HANDLE event=CreateEventW(nullptr,FALSE,FALSE,nullptr);
            if(event){if(SUCCEEDED(fence12_->SetEventOnCompletion(serial_,event)))WaitForSingleObject(event,3000);CloseHandle(event);}
        }
    }
    const std::wstring& error()const{return error_;}
    ID3D11Device* device()const{return device_.Get();}
    ID3D11Texture2D* texture(unsigned index)const{return slots_.at(index).texture.Get();}
    bool open(ID3D12Device* device,const std::vector<ID3D12Resource*>& inputs){
        Ptr<IDXGIFactory4> factory;Ptr<IDXGIAdapter1> adapter;Ptr<ID3D11DeviceContext> immediate;
        if(!check(CreateDXGIFactory1(IID_PPV_ARGS(&factory)),L"DXGI factory")||
           !check(factory->EnumAdapterByLuid(device->GetAdapterLuid(),IID_PPV_ARGS(&adapter)),L"matching adapter")||
           !check(D3D11CreateDevice(adapter.Get(),D3D_DRIVER_TYPE_UNKNOWN,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                    nullptr,0,D3D11_SDK_VERSION,&device_,nullptr,&immediate),L"native device")||
           !check(immediate.As(&context_),L"fence context"))return false;
        Ptr<ID3D11Device5> device5;
        if(!check(device_.As(&device5),L"fence device")||
           !check(device5->CreateFence(0,D3D11_FENCE_FLAG_SHARED,IID_PPV_ARGS(&fence11_)),L"shared fence"))return false;
        HANDLE handle=nullptr;
        if(!check(fence11_->CreateSharedHandle(nullptr,GENERIC_ALL,nullptr,&handle),L"fence handle"))return false;
        auto hr=device->OpenSharedHandle(handle,IID_PPV_ARGS(&fence12_));CloseHandle(handle);
        if(!check(hr,L"open fence"))return false;
        D3D12_COMMAND_QUEUE_DESC q{};q.Type=D3D12_COMMAND_LIST_TYPE_DIRECT;
        if(!check(device->CreateCommandQueue(&q,IID_PPV_ARGS(&queue_)),L"copy queue"))return false;
        slots_.resize(inputs.size());
        for(size_t i=0;i<inputs.size();++i){
            auto& slot=slots_[i];slot.source=inputs[i];const auto desc=inputs[i]->GetDesc();
            D3D11_TEXTURE2D_DESC td{};td.Width=UINT(desc.Width);td.Height=desc.Height;td.MipLevels=td.ArraySize=1;
            td.Format=desc.Format;td.SampleDesc.Count=1;td.Usage=D3D11_USAGE_DEFAULT;
            td.BindFlags=D3D11_BIND_SHADER_RESOURCE;td.MiscFlags=D3D11_RESOURCE_MISC_SHARED|D3D11_RESOURCE_MISC_SHARED_NTHANDLE;
            Ptr<IDXGIResource1> shared;
            if(!check(device_->CreateTexture2D(&td,nullptr,&slot.texture),L"shared input texture")||
               !check(slot.texture.As(&shared),L"shared texture interface")||
               !check(shared->CreateSharedHandle(nullptr,DXGI_SHARED_RESOURCE_READ|DXGI_SHARED_RESOURCE_WRITE,nullptr,&handle),L"texture handle"))return false;
            hr=device->OpenSharedHandle(handle,IID_PPV_ARGS(&slot.shared));CloseHandle(handle);
            if(!check(hr,L"open input texture")||
               !check(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,IID_PPV_ARGS(&slot.allocator)),L"allocator")||
               !check(device->CreateCommandList(0,D3D12_COMMAND_LIST_TYPE_DIRECT,slot.allocator.Get(),nullptr,IID_PPV_ARGS(&slot.list)),L"command list")||
               !check(slot.list->Close(),L"close initial list"))return false;
        }
        return true;
    }
    bool copy(unsigned index,ID3D12Fence* producer,uint64_t value){
        auto& slot=slots_.at(index);
        // The slot's prior NVENC output was consumed before reuse; therefore
        // its previous copy completed and its allocator is safe to reset.
        if(!check(slot.allocator->Reset(),L"reset allocator")||!check(slot.list->Reset(slot.allocator.Get(),nullptr),L"reset list"))return false;
        D3D12_RESOURCE_BARRIER b[2]{};
        for(auto& barrier:b){barrier.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;barrier.Transition.Subresource=D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;barrier.Transition.StateBefore=D3D12_RESOURCE_STATE_COMMON;}
        b[0].Transition.pResource=slot.source.Get();b[0].Transition.StateAfter=D3D12_RESOURCE_STATE_COPY_SOURCE;
        b[1].Transition.pResource=slot.shared.Get();b[1].Transition.StateAfter=D3D12_RESOURCE_STATE_COPY_DEST;
        slot.list->ResourceBarrier(2,b);slot.list->CopyResource(slot.shared.Get(),slot.source.Get());
        for(auto& barrier:b)std::swap(barrier.Transition.StateBefore,barrier.Transition.StateAfter);
        slot.list->ResourceBarrier(2,b);
        if(!check(slot.list->Close(),L"close copy")||!check(queue_->Wait(producer,value),L"producer GPU wait"))return false;
        ID3D12CommandList* lists[]={slot.list.Get()};queue_->ExecuteCommandLists(1,lists);
        if(!check(queue_->Signal(fence12_.Get(),++serial_),L"copy signal")||
           !check(context_->Wait(fence11_.Get(),serial_),L"encoder GPU wait"))return false;
        context_->Flush();return true;
    }
};
}
