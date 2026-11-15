// SPDX-License-Identifier: GPL-3.0-only
#include "veyra/engine/FrameGenerationSelection.h"
#include "veyra/engine/ExportFeaturePolicy.h"
#include "veyra/engine/PresetLibrary.h"
#include "veyra/engine/PresetStore.h"
#include <cstdio>
#include <fstream>
using namespace veyra::engine;
int wmain(int argc,wchar_t** argv){
    if(argc<2||argc>3)return 2;
    const std::filesystem::path root(argv[1]);std::filesystem::create_directories(root);
    unsigned failed=0,checks=0;auto check=[&](bool ok,const char* label){++checks;if(!ok){++failed;std::printf("FAIL %s\n",label);}};
    for(unsigned multiplier:{2u,3u,4u,6u}){
        EnhancementSettings s;s.frameGenerationBackend=FrameGenerationBackend::Anr;s.multiplier=multiplier;
        check(s.validate().empty(),"ANR settings valid");
        check(motionUsesFlow(MotionSource::Automatic,s.frameGenerationBackend),"ANR uses estimated guidance");
        check(crossVendorFrameGeneration(s.frameGenerationBackend),"ANR cross vendor");
        check(exportFrameGenerationSupported(s.frameGenerationBackend,false),"ANR cross vendor export");
        auto session=ChainSession::initial(s);ChainSession restored;
        const auto path=root/(std::to_wstring(multiplier)+L".session");ChainSessionStore writer(path);
        check(writer.save(session),"session atomic save");ChainSessionStore reader(path);
        check(std::filesystem::exists(std::filesystem::path(path).concat(L".vfg")),"ANR versioned session file");
        check(reader.load(restored)&&restored==session,"session restart");
        PresetStore presets(root/(std::to_wstring(multiplier)+L".presets"));
        check(presets.put(L"ANR",s),"legacy preset save");PresetStore reload(root/(std::to_wstring(multiplier)+L".presets"));
        check(reload.load()&&reload.entries().size()==1&&reload.entries()[0].settings.frameGenerationBackend==FrameGenerationBackend::Anr,"legacy preset restart");
    }
    if(argc>2){
        const std::filesystem::path fixtures(argv[2]);
        const auto legacyPreset=root/L"legacy.presets";
        std::filesystem::copy_file(fixtures/L"2.presets",legacyPreset);
        PresetStore legacy(legacyPreset);
        check(legacy.load()&&legacy.entries().size()==1&&legacy.entries()[0].settings.frameGenerationBackend==FrameGenerationBackend::Anr,"pre-2.1.6 ANR preset v37 migration");
        check(legacy.save(),"migrated ANR preset saves in current schema");
        PresetStore again(legacyPreset);check(again.load()&&again.entries().size()==1,"migrated preset restarts");
        const auto legacySession=root/L"legacy.session";
        const auto sidecar=std::filesystem::path(legacySession).concat(L".anr");
        std::filesystem::copy_file(fixtures/L"2.session.anr",sidecar);
        const auto bytes=[](const auto& p){std::ifstream in(p,std::ios::binary);return std::string(std::istreambuf_iterator<char>(in),{});};
        const auto before=bytes(sidecar);
        ChainSession oldSession;ChainSessionStore reader(legacySession);
        check(reader.load(oldSession)&&oldSession.configurations[0].fgBackend==FrameGenerationBackend::Anr,"pre-2.1.6 ANR session v16 migration");
        check(reader.save(oldSession),"legacy session saves to upgraded sidecar");
        check(bytes(sidecar)==before,"legacy ANR sidecar retained byte-for-byte");
        ChainSession recovered;ChainSessionStore restart(legacySession);
        check(restart.load(recovered)&&recovered==oldSession,"upgraded ANR session restarts");
        EnhancementSettings mixed;mixed.frameGenerationBackend=FrameGenerationBackend::Anr;mixed.multiplier=2;
        mixed.exclusion.enabled=true;mixed.exclusion.regions[0]={.1f,.2f,.4f,.6f,true};
        PresetStore masks(root/L"anr-masks.presets");check(masks.put(L"ANR masks",mixed),"ANR with 2.1.6 exclusion mask saves");
        PresetStore masksAgain(root/L"anr-masks.presets");
        check(masksAgain.load()&&masksAgain.entries().size()==1&&masksAgain.entries()[0].settings.exclusion==mixed.exclusion,"ANR ellipse exclusion mask restarts");
    }
    FrameGenerationAvailability caps{true,true,true,true,true,true};
    check(restoredFrameGenerationBackend(FrameGenerationBackend::Anr,caps)==FrameGenerationBackend::Anr,"retain available manual choice");
    caps.anr=false;caps.fsr4=false;
    check(restoredFrameGenerationBackend(FrameGenerationBackend::Anr,caps)==FrameGenerationBackend::Fsr,"missing ANR safe fallback");
    auto invalid=EnhancementSettings{};invalid.frameGenerationBackend=FrameGenerationBackend(7);
    check(!invalid.validate().empty(),"unknown backend rejected");
    std::printf("ANR settings checks=%u failed=%u\n",checks,failed);return failed?1:0;
}
