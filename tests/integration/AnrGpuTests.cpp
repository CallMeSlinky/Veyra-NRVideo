// SPDX-License-Identifier: GPL-3.0-only
// Diagnostic readback verifies actual model pixels, not just successful calls.
#include "veyra/ngx/AnrFgBackend.h"
#include "veyra/pipeline/GpuPassUtils.h"
#include "veyra/gfx/D3D12DeviceContext.h"
#include "veyra/gfx/CommandSlotRing.h"
#include <cstdio>
#include <cmath>
#include <cstring>
#include <set>
#include <d3d12sdklayers.h>
using namespace veyra;
int wmain(int argc,wchar_t** argv) {
    if(argc<2||argc>3)return 2;
    const std::wstring scaleMode=argc==3?argv[2]:L"default";
    constexpr unsigned w=1280,h=720;
    gfx::D3D12DeviceContext ctx;Status status=Status::Ok;gfx::DeviceContextDesc desc{};
    desc.enableDebugLayer=true;desc.commandSlotCount=4;
    if(!ctx.initialize(desc,status))return 2;
    gfx::CommandSlotRing ring;
    if(!ring.initialize(ctx.device(),ctx.directQueue(),ctx.fence(),ctx.fenceEvent(),4,status))return 2;
    Microsoft::WRL::ComPtr<ID3D12InfoQueue> debug;ctx.device()->QueryInterface(IID_PPV_ARGS(&debug));
    unsigned failed=0,checks=0;
    auto check=[&](bool ok,const char* what){++checks;if(!ok){++failed;std::printf("FAIL %s\n",what);}};
    for(auto format:{DXGI_FORMAT_R8G8B8A8_UNORM,DXGI_FORMAT_R10G10B10A2_UNORM}){
        auto input=pipeline::makeTexture(ctx.device(),w,h,format,false);
        auto output=pipeline::makeTexture(ctx.device(),w,h,format,true);
        auto depth=pipeline::makeTexture(ctx.device(),w,h,DXGI_FORMAT_R32_FLOAT,false);
        auto motion=pipeline::makeTexture(ctx.device(),w,h,DXGI_FORMAT_R16G16_FLOAT,false);
        if(!input||!output||!depth||!motion)return 2;
        auto td=input->GetDesc();D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp{};UINT rows=0;UINT64 rowBytes=0,total=0;
        ctx.device()->GetCopyableFootprints(&td,0,1,0,&fp,&rows,&rowBytes,&total);
        auto upload=pipeline::makeUploadBuffer(ctx.device(),total*10);
        D3D12_HEAP_PROPERTIES hp{};hp.Type=D3D12_HEAP_TYPE_READBACK;
        D3D12_RESOURCE_DESC bd{};bd.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;bd.Width=total;bd.Height=1;bd.DepthOrArraySize=1;bd.MipLevels=1;bd.SampleDesc.Count=1;bd.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        Microsoft::WRL::ComPtr<ID3D12Resource> readback;
        if(!upload||FAILED(ctx.device()->CreateCommittedResource(&hp,D3D12_HEAP_FLAG_NONE,&bd,D3D12_RESOURCE_STATE_COPY_DEST,nullptr,IID_PPV_ARGS(&readback))))return 2;
        void* data=nullptr;if(FAILED(upload->Map(0,nullptr,&data)))return 2;
        std::set<uint64_t> sourceHashes;
        for(unsigned frame=0;frame<8;++frame){
            uint64_t hash=1469598103934665603ull;
            for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x){
                const bool box=x>=w/3+frame*8&&x<w/3+frame*8+100&&y>h/3&&y<h*2/3;
                const unsigned r=box?230:24+x*20/w,g=box?180:30+y*20/h,b=box?40:48;
                const uint32_t pixel=format==DXGI_FORMAT_R8G8B8A8_UNORM?r|(g<<8)|(b<<16)|0xff000000u:
                    (r*1023/255)|((g*1023/255)<<10)|((b*1023/255)<<20)|(3u<<30);
                std::memcpy(static_cast<unsigned char*>(data)+frame*total+y*fp.Footprint.RowPitch+x*4,&pixel,4);
                hash=(hash^pixel)*1099511628211ull;
            }
            sourceHashes.insert(hash);
        }
        for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x){
            const float z=1.0f;const uint32_t flow=0x0000c800; // half2(-8, 0) pixels
            std::memcpy(static_cast<unsigned char*>(data)+8*total+y*fp.Footprint.RowPitch+x*4,&z,4);
            std::memcpy(static_cast<unsigned char*>(data)+9*total+y*fp.Footprint.RowPitch+x*4,&flow,4);
        }
        upload->Unmap(0,nullptr);
        pipeline::StateTracker guidanceTracker,tracker;
        for(unsigned multiplier:{2u,3u,4u,6u}){
            ngx::AnrFgBackend anr;auto* list=ring.acquire(0,status);if(!list)return 2;
            if(!anr.initialize(ctx.device(),list,argv[1],w,h,format,multiplier)){std::puts("FAIL initialize");return 1;}
            if(!ring.submitAndSignal(0)||!ring.waitIdle())return 2;
        {list=ring.acquire(0,status);if(!list)return 2;
            for(unsigned i=0;i<2;++i){auto* target=i?motion.Get():depth.Get();
                guidanceTracker.transition(list,target,D3D12_RESOURCE_STATE_COPY_DEST);
                D3D12_TEXTURE_COPY_LOCATION src{},dst{};src.pResource=upload.Get();src.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;src.PlacedFootprint=fp;src.PlacedFootprint.Footprint.Format=i?DXGI_FORMAT_R16G16_FLOAT:DXGI_FORMAT_R32_FLOAT;src.PlacedFootprint.Offset=(8+i)*total;
                dst.pResource=target;dst.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
                list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);
                guidanceTracker.transition(list,target,D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
            }
            if(!ring.submitAndSignal(0)||!ring.waitIdle())return 2;
        }
            std::set<uint64_t> generated;
            for(unsigned frame=0;frame<8;++frame){
                list=ring.acquire(0,status);if(!list)return 2;
                tracker.transition(list,input.Get(),D3D12_RESOURCE_STATE_COPY_DEST);
                D3D12_TEXTURE_COPY_LOCATION src{},dst{};src.pResource=upload.Get();src.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;src.PlacedFootprint=fp;src.PlacedFootprint.Offset=frame*total;
                dst.pResource=input.Get();dst.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
                list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);
                tracker.transition(list,input.Get(),D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
                // The product submits its color producer before calling ANR.
                // Isolate that ordering from the provider's native interop.
                if(!ring.submitAndSignal(0)||!ring.waitIdle())return 2;
                list=ring.acquire(0,status);if(!list)return 2;
                tracker.transition(list,output.Get(),D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
                guidanceTracker.transition(list,depth.Get(),D3D12_RESOURCE_STATE_COPY_DEST);
                guidanceTracker.transition(list,motion.Get(),D3D12_RESOURCE_STATE_COPY_DEST);
                for(unsigned sub=1;sub<multiplier;++sub){
                    ngx::DlssFgBackend::EvalDesc d{};d.backbuffer=input.Get();d.outputInterpolated=output.Get();
                    d.depth=depth.Get();d.mvecs=motion.Get();d.mvecScaleX=-1.0f/w;d.mvecScaleY=-1.0f/h;
                    if(scaleMode==L"positive"){d.mvecScaleX=1.0f/w;d.mvecScaleY=1.0f/h;}
                    if(scaleMode==L"pixels-positive"){d.mvecScaleX=1.0f;d.mvecScaleY=1.0f;}
                    if(scaleMode==L"pixels-negative"){d.mvecScaleX=-1.0f;d.mvecScaleY=-1.0f;}
                    d.hdr=format==DXGI_FORMAT_R10G10B10A2_UNORM;d.reset=frame==0;d.frameId=frame+1;
                    d.multiFrameCount=multiplier-1;d.multiFrameIndex=sub;
                    if(!anr.evaluate(list,d))return 1;
                    tracker.uavBarrier(list,output.Get());
                }
                // Native interop can schedule output copies at ExecuteCommandLists.
                // Observe the completed generated texture in a subsequent list.
                if(!ring.submitAndSignal(0)||!ring.waitIdle())return 2;
                list=ring.acquire(0,status);if(!list)return 2;
                tracker.transition(list,output.Get(),D3D12_RESOURCE_STATE_COPY_SOURCE);
                src={};src.pResource=output.Get();src.Type=D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
                dst={};dst.pResource=readback.Get();dst.Type=D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;dst.PlacedFootprint=fp;
                list->CopyTextureRegion(&dst,0,0,0,&src,nullptr);
                if(!ring.submitAndSignal(0)||!ring.waitIdle())return 2;
                if(frame>1){
                    D3D12_RANGE range{0,size_t(total)};void* pixels=nullptr;
                    if(FAILED(readback->Map(0,&range,&pixels)))return 2;
                    uint64_t hash=1469598103934665603ull,energy=0;
                    double weight=0,weightedX=0;
                    for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x){
                        uint32_t pixel=0;std::memcpy(&pixel,static_cast<unsigned char*>(pixels)+y*fp.Footprint.RowPitch+x*4,4);
                        hash=(hash^pixel)*1099511628211ull;energy+=pixel&255;
                        const unsigned red=format==DXGI_FORMAT_R8G8B8A8_UNORM?pixel&255:(pixel&1023)*255/1023;
                        if(red>100){const double value=red-100;weight+=value;weightedX+=value*x;}
                    }
                    readback->Unmap(0,nullptr);generated.insert(hash);
                    check(energy>1000,"output is nonblack");check(!sourceHashes.contains(hash),"output differs from every source frame");
                    const double expected=double(w/3)+(frame-1)*8+49.5+8.0*(multiplier-1)/multiplier;
                    std::printf("ANR_PHASE format=%u multiplier=%u frame=%u centroid=%.4f expected=%.4f current=%.4f\n",unsigned(format),multiplier,frame,weight?weightedX/weight:0,expected,double(w/3)+frame*8+49.5);
                    if(format==DXGI_FORMAT_R8G8B8A8_UNORM&&frame>=3)
                        check(weight>0&&std::abs(weightedX/weight-expected)<0.3,"object position matches temporal subframe");
                }
            }
            check(generated.size()>1,"generated pixels change with motion");
            check(anr.shutdown(),"release and shutdown");
            std::printf("format=%u multiplier=%u distinct=%zu\n",unsigned(format),multiplier,generated.size());
        }
    }
    if(debug){
        unsigned errors=0;
        for(UINT64 i=0;i<debug->GetNumStoredMessagesAllowedByRetrievalFilter();++i){
            SIZE_T bytes=0;debug->GetMessage(i,nullptr,&bytes);std::vector<unsigned char> storage(bytes);
            auto* message=reinterpret_cast<D3D12_MESSAGE*>(storage.data());debug->GetMessage(i,message,&bytes);
            if(message->Severity<=D3D12_MESSAGE_SEVERITY_ERROR){++errors;std::printf("D3D12 %s\n",message->pDescription);}
        }
        check(errors==0,"D3D12 debug errors");
    }
    std::printf("ANR GPU checks=%u failed=%u\n",checks,failed);return failed?1:0;
}
