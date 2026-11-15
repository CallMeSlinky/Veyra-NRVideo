// Diagnostic only: paced file arrival through the actual live scheduler.
// No physical capture device, controller or display scanout measurement.
#include "veyra/engine/EngineController.h"
#include "veyra/Log.h"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <thread>

int wmain(int argc, wchar_t** argv) {
    using namespace veyra::engine;
    using Clock = std::chrono::steady_clock;
    if (argc != 6) return 2; // input, evidence, backend, VFG quality, seconds
    const std::wstring backend = argv[3];
    const int quality = _wtoi(argv[4]), seconds = _wtoi(argv[5]);
    if (quality < 0 || quality > 2 || seconds < 3 || seconds > 60) return 2;
    if (backend != L"off" && backend != L"dlss" && backend != L"xess" && backend != L"vfg" && backend != L"anr") return 2;
    const std::filesystem::path dir = argv[2];
    std::filesystem::create_directories(dir);
    SetEnvironmentVariableW(L"VEYRA_TEST_REPLAY_AS_CARD", L"1");
    SetEnvironmentVariableW(L"VEYRA_VERBOSE_FRAME_LOGS", L"0");
    veyra::Logger::instance().openFile((dir / L"engine.log").wstring());
    veyra::Logger::instance().setConsoleEnabled(false);
    if (FAILED(CoInitializeEx(nullptr, COINIT_MULTITHREADED))) return 2;
    HWND window = CreateWindowExW(0, L"STATIC", L"Veyra FG software latency probe", WS_OVERLAPPEDWINDOW | WS_VISIBLE,
        40, 40, 1280, 760, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    if (!window) return 2;
    MONITORINFOEXW monitor{}; monitor.cbSize = sizeof(monitor);
    GetMonitorInfoW(MonitorFromWindow(window, MONITOR_DEFAULTTONEAREST), &monitor);
    DEVMODEW dm{}; dm.dmSize = sizeof(dm); EnumDisplaySettingsW(monitor.szDevice, ENUM_CURRENT_SETTINGS, &dm);
    std::cout << "display=" << dm.dmPelsWidth << 'x' << dm.dmPelsHeight << '@' << dm.dmDisplayFrequency << '\n';
    int result = 0;
    {
        EngineController engine; engine.setVolume(0, true);
        PresentationSettings presentation;
        presentation.enabled = true;
        presentation.nvidiaLowLatency = NvidiaLowLatency::On;
        presentation.display = DisplaySync::Automatic;
        engine.requestPresentation(presentation);
        EnhancementSettings settings;
        settings.nr = false; settings.sr = false;
        settings.multiplier = backend == L"off" ? 1 : 2;
        settings.frameGenerationBackend = backend == L"xess" ? FrameGenerationBackend::XeSS :
            backend == L"vfg" ? FrameGenerationBackend::Vfg : backend == L"anr" ? FrameGenerationBackend::Anr : FrameGenerationBackend::Dlss;
        settings.vfgQuality = quality;
        settings.vfgAutoRegulate = false; // keep each requested model fixed
        settings.content = ContentRate::Auto;
        auto options = PlayerOptions::from(settings); options.captureReplayForTest = true;
        engine.open(window, argv[1], options);
        auto pump = [] { MSG msg; while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); } };
        auto deadline = Clock::now() + std::chrono::seconds(40);
        auto last = engine.snapshot();
        while (Clock::now() < deadline) {
            pump(); last = engine.snapshot();
            if (last.failed || (last.frames > 90 && (backend == L"off" || last.fgActive))) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        if (last.failed || last.frames <= 90 || (backend != L"off" && !last.fgActive)) {
            std::wcerr << L"FAIL warmup " << last.status << '\n'; result = 3;
        } else {
            std::ofstream csv(dir / L"samples.csv"); csv << std::setprecision(9);
            csv << "wall,frames,generated,realPresented,generatedPresented,xessPresented,xessGenerated,fgSkipped,fgExpired,sourceSkipped,fgActive,limited,contentFps,softwareMean,softwareP95,latencySamples,enhancementMean,fgGpuMean,flowGpuMean,pairInterval,generatedFromA,generatedFromB,ageP95,submitFps,pending,providerOwned\n";
            const auto start = Clock::now(); const auto first = last;
            while (Clock::now() - start < std::chrono::seconds(seconds)) {
                pump(); last = engine.snapshot();
                if (last.failed || (backend != L"off" && (!last.fgActive || last.applied.frameGenerationBackend != settings.frameGenerationBackend))) { result = 4; break; }
                const auto& f = last.metrics.flow; const auto& c = f.counters;
                auto value = [](const auto& v) { return v.value_or(-1.0); };
                csv << std::chrono::duration<double>(Clock::now() - start).count() << ',' << last.frames << ',' << last.generated << ','
                    << c.realPresented << ',' << c.generatedPresented << ',' << c.xessSdkPresented << ',' << c.xessSdkGenerated << ','
                    << c.fgSkippedBeforeEval << ',' << c.generatedExpiredAfterEval << ',' << c.sourceSkippedBeforeGraph << ','
                    << last.fgActive << ',' << last.fgBudgetLimited << ',' << last.contentFps << ','
                    << value(f.softwareLatencyMs) << ',' << value(f.softwareLatencyP95Ms) << ',' << f.latencySamples << ','
                    << value(f.enhancementProcessing.mean) << ',' << value(f.gpuTiming[size_t(veyra::diagnostics::GpuStage::FgBatch)].mean) << ','
                    << value(f.gpuTiming[size_t(veyra::diagnostics::GpuStage::Flow)].mean) << ','
                    << value(f.pairTiming[0].mean) << ',' << value(f.pairTiming[1].mean) << ',' << value(f.pairTiming[2].mean) << ','
                    << last.captureAgeP95Ms << ',' << value(last.submissionFps) << ',' << f.pendingOutputFrames << ',' << last.presentationProviderOwned << '\n';
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
            }
            const double elapsed = std::chrono::duration<double>(Clock::now() - start).count();
            std::cout << "seconds=" << elapsed << " sourceFps=" << (last.frames - first.frames) / elapsed
                << " sourceDelta=" << last.frames - first.frames << " generatedDelta=" << last.generated - first.generated
                << " contentFps=" << last.contentFps << " active=" << last.fgActive << " limited=" << last.fgBudgetLimited << '\n';
            if (last.frames < first.frames + unsigned(seconds * 20)) result = 5;
        }
        engine.stop();
        deadline = Clock::now() + std::chrono::seconds(15);
        while (!engine.idle() && Clock::now() < deadline) { pump(); std::this_thread::sleep_for(std::chrono::milliseconds(10)); }
        if (!engine.idle()) result = 6;
    }
    DestroyWindow(window); CoUninitialize();
    std::cout << "RESULT " << result << std::endl;
    return result;
}
