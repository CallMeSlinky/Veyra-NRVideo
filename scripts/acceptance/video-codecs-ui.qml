// Loaded only in the build copy of Main.qml, with a task-specific data directory.
import QtQuick
Item {
    id: test
    property string media: ""
    property string directory: ""
    property int codec: 2
    property bool restart: false
    property int step: 0
    property int ticks: 0
    property int waited: 0
    property var appWindow: Window.window
    function check(ok, why) { if (!ok) throw new Error(why) }
    function find(item, name) {
        if(item.objectName===name)return item
        for(const child of item.children||[]) { const got=find(child,name);if(got)return got }
        return null
    }
    function next(value) { step=value;waited=0 }
    Timer {
        id: timer
        running: true; repeat: true; interval: 250
        onTriggered: { try {
            test.ticks++;test.waited++
            test.check(test.ticks<180,"codec acceptance timeout")
            if(test.step===0) {
                if(test.restart) {
                    test.check(veyra.recordingCodec===test.codec,"recording codec persists after restart")
                    console.log("VIDEO_CODEC_RESTART_PASS");timer.stop();Qt.quit();return
                }
                // A legacy preference must remain readable before a new selection.
                test.check(veyra.setPreference("recordHevc",true)&&veyra.recordingCodec===1,"legacy HEVC preference")
                test.check(veyra.setPreference("recordCodec",test.codec),"codec preference saves")
                test.check(!veyra.setPreference("recordCodec",3)&&!veyra.setPreference("recordCodec",-1),"invalid codec rejected")
                test.check(veyra.recordingCodec===test.codec,"invalid request preserves choice")
                test.appWindow.page="set"
                const control=test.find(test.appWindow.contentItem,"set-rechevc")
                test.check(control&&control.options.length===3,"three recording codec choices")
                control.picked(String(test.codec))
                test.check(veyra.recordingCodec===test.codec,"recording control uses codec IDs")
                veyra.exportCodec=test.codec
                test.check(veyra.exportCodec===test.codec&&veyra.exportHevc===(test.codec===1),"export codec bridge")
                veyra.exportHevc=true
                test.check(veyra.exportCodec===1,"legacy export setter")
                veyra.exportCodec=test.codec
                test.check(veyra.setPreference("recordDir",test.directory),"recording directory")
                veyra.setPreference("recordAudio",false);veyra.setPreference("recordMic",false)
                veyra.setPreference("recordFps",30);veyra.setPreference("replaySeconds",15)
                veyra.nrEnabled=false;veyra.srEnabled=false;veyra.fgEnabled=false;veyra.muted=true
                veyra.setPreference("replayEnabled",true)
                veyra.openPath(test.media);test.next(1)
            } else if(test.step===1) {
                test.check(!veyra.replayState.failed,"replay: "+veyra.replayState.error)
                if(!veyra.running||veyra.replayState.seconds<3)return
                veyra.startRecording("codec-acceptance");test.next(2)
            } else if(test.step===2) {
                test.check(!veyra.recordingState.failed,"recording: "+veyra.recordingState.error)
                if(test.waited<20)return
                test.check(veyra.recording,"recording active")
                veyra.stopRecording("codec-acceptance");veyra.saveReplay("codec-acceptance");test.next(3)
            } else if(test.step===3) {
                test.check(!veyra.replayState.failed,"replay save: "+veyra.replayState.error)
                if(!veyra.replayState.saved||veyra.recordingState.finishing)return
                console.log("VIDEO_CODEC_UI_PASS",test.codec,veyra.replayState.path)
                veyra.setPreference("replayEnabled",false);timer.stop();Qt.quit()
            }
        } catch(error) { console.log("VIDEO_CODEC_UI_FAIL",String(error));timer.stop();Qt.quit() } }
    }
}
