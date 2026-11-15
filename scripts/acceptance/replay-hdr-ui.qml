// Acceptance-only loader, injected into the build copy of Main.qml and restored.
import QtQuick
Item {
    id: test
    property var appWindow: Window.window
    property string media: ""
    property string evidence: ""
    property int step: 0
    property int ticks: 0
    property int waited: 0
    property bool exercisePause: false
    property var frozen: ({})
    property int savedBefore: 0
    function check(ok, why) { if (!ok) throw new Error(why) }
    function find(item, name) {
        if (item.objectName === name) return item
        for (const child of item.children || []) { const got = find(child, name); if (got) return got }
        return null
    }
    function next(value) { step = value; waited = 0 }
    Timer {
        id: timer
        interval: 200; repeat: true; running: true
        onTriggered: { try {
            ++test.ticks; ++test.waited
            test.check(test.ticks < 450, "timeout at step " + test.step)
            if (test.step === 0) {
                if (!test.appWindow) return
                test.check(veyra.version.indexOf("2.1.6") >= 0, "application reports 2.1.6")
                test.check(!veyra.vfgAutoRegulate, "2.1.6 VFG auto-regulation default")
                const choices = veyra.fgBackendChoices
                test.check(choices.find(c => c.id === "anr").label === "Apex ANR · Beta", "local ANR label preserved")
                const vfg = choices.find(c => c.id === "vfg")
                test.check(!vfg.gold && !vfg.label.includes("👑"), "original VFG dropdown label preserved")
                veyra.contentRate = 3
                test.check(veyra.contentRate === 1, "old content mode migrates to automatic")
                veyra.contentRate = 5
                test.check(veyra.contentRate === 5, "60-to-30 mode accepted")
                veyra.contentRate = 1
                veyra.nvidiaLowLatency = 2
                test.check(veyra.nvidiaLowLatency === 1, "old Boost value migrates to On")
                veyra.setPreference("recordDir", test.evidence + "/clips")
                veyra.setPreference("autoResume", false)
                veyra.setPreference("recordAudio", test.exercisePause)
                veyra.setPreference("recordMic", false)
                veyra.setPreference("replaySeconds", 15)
                veyra.nrEnabled = false; veyra.srEnabled = false; veyra.fgEnabled = false
                veyra.muted = true
                test.appWindow.page = "set"
                const toggle = test.find(test.appWindow.contentItem, "set-hdr-advanced-toggle")
                const body = test.find(test.appWindow.contentItem, "set-hdr-advanced-body")
                test.check(toggle && body, "HDR controls exist")
                test.check(!body.visible, "HDR starts collapsed")
                toggle.clicked()
                // The playback settings section is hidden here; inspect explicit visibility
                // after selecting its owning page rather than treating hidden ancestors as failure.
                let settings = toggle
                while (settings && settings.hdrAdvancedExpanded === undefined) settings = settings.parent
                test.check(settings && settings.hdrAdvancedExpanded, "HDR expands")
                settings.section = "play"
                test.check(body.visible, "HDR controls visible in playback settings")
                const strength = veyra.hdrCurveStrength
                toggle.clicked(); toggle.clicked()
                test.check(veyra.hdrCurveStrength === strength, "folding preserves HDR values")
                toggle.clicked()
                test.appWindow.page = "pro"
                const dedup = test.find(test.appWindow.contentItem, "list-dedup-enabled")
                const modes = test.find(test.appWindow.contentItem, "list-content-rate")
                test.check(dedup && modes && modes.options.length === 2, "2.1.6 duplicate removal controls")
                modes.picked("5")
                test.check(veyra.contentRate === 5, "duplicate mode dropdown commits 60-to-30")
                dedup.toggled(false)
                test.check(veyra.contentRate === 0, "duplicate removal switch turns off")
                dedup.toggled(true)
                test.check(veyra.contentRate === 5, "duplicate removal switch restores its mode")
                const latency = test.find(test.appWindow.contentItem, "list-nvidia-low-latency")
                test.check(latency && latency.options.length === 2, "low-latency control offers Off and On only")
                const replay = test.find(test.appWindow.contentItem, "pro-replay-toggle")
                test.check(replay, "replay toggle exists beside recording")
                replay.toggled(true)
                test.check(veyra.replayEnabled, "replay toggle updates bridge")
                veyra.openPath(test.media)
                test.next(1)
            } else if (test.step === 1) {
                test.check(!veyra.replayState.failed, "replay encoder: " + veyra.replayState.error)
                if (!veyra.running || veyra.replayState.seconds < 3) return
                veyra.startRecording("replay-hdr-acceptance")
                test.next(2)
            } else if (test.step === 2) {
                if (test.waited < 20) return
                test.check(veyra.recording, "recording runs alongside replay")
                veyra.stopRecording("replay-hdr-acceptance")
                veyra.saveReplay("replay-hdr-acceptance")
                test.next(3)
            } else if (test.step === 3) {
                test.check(!veyra.replayState.failed, "replay save: " + veyra.replayState.error)
                if (!veyra.replayState.saved || veyra.recordingState.finishing) return
                test.check(veyra.replayEnabled && veyra.replayState.active, "buffer continues after saving")
                console.log("REPLAY_HDR_UI_PASS", veyra.replayState.path, veyra.recordingState.path)
                if (test.exercisePause) {
                    veyra.togglePlayPause(); test.next(4); return
                }
                veyra.setPreference("replayEnabled", false)
                timer.stop(); Qt.quit()
            } else if (test.step === 4) {
                if (test.waited < 6 || !veyra.paused) return
                test.check(veyra.replayState.paused, "replay follows source pause")
                test.frozen = Object.assign({}, veyra.replayState)
                test.next(5)
            } else if (test.step === 5) {
                if (test.waited < 100) return // longer than the selected 15-second buffer
                test.check(veyra.replayState.seconds === test.frozen.seconds, "paused replay duration is frozen")
                test.check(veyra.replayState.bytes === test.frozen.bytes, "paused replay memory does not grow")
                test.check(veyra.replayState.frames === test.frozen.frames, "paused redraws are not recorded")
                test.savedBefore = veyra.replayState.saved
                veyra.saveReplay("pause-acceptance"); test.next(6)
            } else if (test.step === 6) {
                if (veyra.replayState.saved <= test.savedBefore) return
                test.check(veyra.replayState.paused, "saving leaves replay paused")
                veyra.togglePlayPause(); test.next(7)
            } else if (test.step === 7) {
                if (test.waited < 20) return
                test.check(!veyra.replayState.paused && veyra.replayState.frames > test.frozen.frames, "replay resumes with playback")
                veyra.togglePlayPause(); test.next(8)
            } else if (test.step === 8) {
                if (test.waited < 6) return
                test.savedBefore = veyra.replayState.saved
                veyra.saveReplay("resume-acceptance"); test.next(9)
            } else if (test.step === 9) {
                if (veyra.replayState.saved <= test.savedBefore) return
                veyra.setPreference("replayEnabled", false)
                veyra.setPreference("replayEnabled", true)
                test.next(10)
            } else if (test.step === 10) {
                if (test.waited < 8) return
                test.check(veyra.replayState.paused && veyra.replayState.seconds === 0 && veyra.replayState.bytes === 0, "enabling replay while paused captures nothing")
                veyra.togglePlayPause(); test.next(11)
            } else if (test.step === 11) {
                if (test.waited < 20 || veyra.replayState.seconds < 2) return
                veyra.stopPlayback(); test.next(12)
            } else if (test.step === 12) {
                if (test.waited < 8 || veyra.running) return
                test.check(veyra.replayState.paused, "idle source freezes replay")
                test.savedBefore = veyra.replayState.saved
                veyra.saveReplay("idle-acceptance"); test.next(13)
            } else if (test.step === 13) {
                if (veyra.replayState.saved <= test.savedBefore) return
                console.log("REPLAY_PAUSE_PASS")
                veyra.setPreference("replayEnabled", false)
                timer.stop(); Qt.quit()
            }
        } catch (error) {
            console.log("REPLAY_HDR_UI_FAIL", String(error)); timer.stop(); Qt.quit()
        } }
    }
}
