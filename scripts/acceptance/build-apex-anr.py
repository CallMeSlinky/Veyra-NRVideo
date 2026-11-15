"""Local Release build; use existing dependencies and keep artifacts on E:."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
# ASCII junction to the mandated artifact root (MSVC/Ninja's command line
# debug records cannot represent the Chinese path under this host's ACP).
ARTIFACTS = Path('E:/Veyra-dev/Veyra/anr-artifacts')
BUILD = ARTIFACTS / 'build/apex-anr-20261112'
VS = Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools')
CMAKE = VS / 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
NINJA = VS / 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'

def environment():
    temp = ARTIFACTS / 'tmp/apex-anr-20261112'
    temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(temp), TMP=str(temp))
    setup = subprocess.run(f'cmd /d /s /c ""{VS / "VC/Auxiliary/Build/vcvars64.bat"}" >nul && set"',
        env=env, capture_output=True, text=True, check=True)
    for line in setup.stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            env[key] = value
    return env

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    arguments = sys.argv[1:]
    label = '2.1.9'
    if '--label' in arguments:
        index = arguments.index('--label')
        label = arguments[index + 1]
        del arguments[index:index + 2]
    BUILD.mkdir(parents=True, exist_ok=True)
    env=environment()
    if sys.argv[1:]==['--opticalflow']:
        source=ARTIFACTS/'deps/apex-anr-20261112/fidelityfx-1.1.4/sdk'
        # Upstream forces a VS-only platform even for Ninja. Keep the SDK's
        # effect code intact; adapt only its local toolchain for this generator.
        toolchain=source/'toolchain.cmake'
        text=toolchain.read_text(encoding='utf-8')
        original=toolchain.with_suffix('.cmake.original')
        if not original.exists(): original.write_text(text,encoding='utf-8')
        text=text.replace('set(CMAKE_GENERATOR_PLATFORM "x64" CACHE STRING "" FORCE)', '# Ninja x64 is selected by the compiler environment')
        toolchain.write_text(text,encoding='utf-8')
        pix=source/'libs/pix/CMakeLists.txt'
        text=pix.read_text(encoding='utf-8')
        if not pix.with_suffix('.txt.original').exists():pix.with_suffix('.txt.original').write_text(text,encoding='utf-8')
        pix.write_text(text.replace('${CMAKE_GENERATOR_PLATFORM}','${FFX_PLATFORM_NAME}'),encoding='utf-8')
        shaders=source/'include/FidelityFX/gpu/CMakeCompileShaders.txt'
        text=shaders.read_text(encoding='utf-8')
        original=shaders.with_suffix('.txt.original')
        if not original.exists():original.write_text(text,encoding='utf-8')
        text=text.replace('PERMUTATION_OUTPUTS)\n','PERMUTATION_OUTPUTS)\n\tset(OUTPUT_VARIABLE ${PERMUTATION_OUTPUTS})\n\tset(PERMUTATION_OUTPUTS "")\n',1) if 'set(OUTPUT_VARIABLE' not in text else text
        text=text.replace('set(${PERMUTATION_OUTPUTS} ${PERMUTATION_OUTPUTS} PARENT_SCOPE)','set(${OUTPUT_VARIABLE} ${PERMUTATION_OUTPUTS} PARENT_SCOPE)')
        shaders.write_text(text,encoding='utf-8')
        build=ARTIFACTS/'build/apex-anr-opticalflow-20261112'
        commands=[[str(CMAKE),'-S',str(source),'-B',str(build),'-G','Ninja',
            f'-DCMAKE_MAKE_PROGRAM={NINJA}','-DCMAKE_BUILD_TYPE=Release',
            '-DFFX_API_BACKEND=DX12_X64','-DFFX_OF=ON','-DFFX_ALL=OFF',
            '-DCMAKE_EXE_LINKER_FLAGS=/machine:x64','-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded'],
            [str(CMAKE),'--build',str(build),'--parallel','2','--target','ffx_opticalflow_x64','ffx_backend_dx12_x64']]
        with (BUILD/'opticalflow-build.log').open('a',encoding='utf-8') as log:
            for command in commands:
                log.write(subprocess.list2cmdline(command)+'\n');log.flush()
                done=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
                if done.returncode:
                    print((BUILD/'opticalflow-build.log').read_text(encoding='utf-8',errors='replace')[-8000:]);return done.returncode
        print('Optical flow SDK build passed');return 0
    configure = [str(CMAKE), '-S', str(ROOT), '-B', str(BUILD), '-G', 'Ninja',
        f'-DCMAKE_MAKE_PROGRAM={NINJA}', '-DCMAKE_BUILD_TYPE=Release',
        f'-DVEYRA_DISPLAY_VERSION={label}', '-DVEYRA_ENABLE_D3D12_DEBUG=OFF',
        '-DVEYRA_ENABLE_EXPERIMENTAL_DLSSNR=ON', '-DVEYRA_ENABLE_NVOF=ON',
        '-DVEYRA_BUILD_QML_UI=ON',
        f'-DVEYRA_CUDA_DRIVER_INCLUDE_DIR=C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.5/include',
        f'-DVEYRA_XESS_ROOT={ARTIFACTS / "deps/apex-anr-20261112/xess-3.0.2"}',
        f'-DVEYRA_FIDELITYFX_ROOT={ARTIFACTS / "deps/apex-anr-20261112/fidelityfx-1.1.4/sdk"}',
        f'-DVEYRA_FIDELITYFX2_ROOT={ARTIFACTS / "deps/apex-anr-20261112/fidelityfx-2.3.0/Kits/FidelityFX"}',
        f'-DVEYRA_DLSS_SDK_ROOT={ROOT / "deps/nvidia/DLSS-310.7.0"}',
        f'-DVEYRA_NVOF_SDK_ROOT={ROOT / "deps/nvidia/Optical_Flow_SDK_5.0.7"}',
        f'-DVEYRA_NVENC_HEADERS_ROOT={ROOT / "deps/nvidia/nv-codec-headers-13.0.19.0"}',
        f'-DCMAKE_PREFIX_PATH={ROOT / "deps/qt/6.8.3/msvc2022_64"}',
        '-DVEYRA_FFMPEG_ROOT=E:/Veyra-dev/Veyra/deps/ffmpeg-9.0.1-veyra']
    amf = ARTIFACTS / 'deps/amf-sdk-1.5.3-20261115/amf/public'
    if (amf / 'include/components/FRC.h').is_file():
        configure.append(f'-DVEYRA_AMF_SDK_ROOT={amf}')
    targets = arguments or ['veyra_qml_ui']
    with (BUILD / 'anr-build.log').open('a', encoding='utf-8') as log:
        for command in [configure, [str(CMAKE), '--build', str(BUILD), '--parallel', '2', '--target', *targets]]:
            log.write(subprocess.list2cmdline(command) + '\n'); log.flush()
            done = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            if done.returncode:
                print((BUILD / 'anr-build.log').read_text(encoding='utf-8', errors='replace')[-10000:])
                return done.returncode
    print('Build passed:', ', '.join(targets), '\nLog:', BUILD / 'anr-build.log')
    return 0

if __name__ == '__main__':
    sys.exit(main())
