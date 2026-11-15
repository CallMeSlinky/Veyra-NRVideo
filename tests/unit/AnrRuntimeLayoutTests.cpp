// SPDX-License-Identifier: GPL-3.0-only
#include "veyra/ngx/AnrRuntimeLayout.h"
#include <fstream>
#include <iostream>

int main(int argc,char** argv) {
    if(argc!=2)return 2;
    namespace fs=std::filesystem;
    const fs::path root=fs::absolute(argv[1]);
    if(fs::exists(root))return 2;
    fs::create_directories(root);
    unsigned checks=0,failed=0;
    auto check=[&](bool value,const char* description){++checks;if(!value){++failed;std::cerr<<description<<'\n';}};
    auto populate=[](const fs::path& directory){
        for(const auto* name:{"nvngx_dlssg.dll","nr_fg.ini","path_table.json","size_table.json",
                "adapters/pack.nrx","kernels/pack.nrx","kernels-portable/pack.nrx",
                "programs/fg-lite-any-portable-srgb8/pack.nrx","programs/fg-lite-any-portable-pq10/pack.nrx"}){
            const auto path=directory/name;fs::create_directories(path.parent_path());std::ofstream(path)<<"fixture";
        }
    };
    const auto experimental=root/"runtime/experimental",base=root/"runtime/anr";
    const auto full=base/"game/OptiScaler/custom/Apex Neural Rendering FG/dlssg";
    check(!veyra::ngx::completeAnrRuntime(veyra::ngx::anrRuntimeDirectory(experimental)),"missing runtime unavailable");
    fs::create_directories(base/"game");std::ofstream(base/"game/dxgi.dll")<<"not ANR";
    check(!veyra::ngx::completeAnrRuntime(veyra::ngx::anrRuntimeDirectory(experimental)),"OptiScaler proxy alone is not ANR");
    populate(full);
    check(veyra::ngx::anrRuntimeDirectory(experimental)==full,"find untouched full ZIP layout");
    check(veyra::ngx::completeAnrRuntime(full),"full package is complete");
    fs::rename(full/"kernels/pack.nrx",full/"kernels/pack.nrx.disabled");
    check(!veyra::ngx::completeAnrRuntime(veyra::ngx::anrRuntimeDirectory(experimental)),"incomplete provider unavailable");
    populate(base);
    check(veyra::ngx::anrRuntimeDirectory(experimental)==base,"legacy flat install still works");
    populate(full);
    check(veyra::ngx::anrRuntimeDirectory(experimental)==base,"complete flat install has stable precedence");
    std::cout<<"ANR layout checks="<<checks<<" failed="<<failed<<'\n';
    return failed?1:0;
}
