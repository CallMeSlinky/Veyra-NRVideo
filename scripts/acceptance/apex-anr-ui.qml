// Loaded only into the disposable acceptance application; never shipped.
import QtQuick
Item {
    id: test
    property var appWindow: Window.window
    property string media: ""
    property string evidence: ""
    property string phase: "run"
    property int step: 0
    property int ticks: 0
    property int waited: 0
    property string firstScreenshot: ""
    function check(ok,why) { if (!ok) throw new Error(why) }
    function find(item,name) { if(item.objectName===name)return item;for(const child of item.children||[]){const got=find(child,name);if(got)return got}return null }
    function pro(item) { if(item.objectName==="pro-page"||typeof item.applySelectedPreset==="function")return item;for(const child of item.children||[]){const got=pro(child);if(got)return got}return null }
    function next(value) {step=value;waited=0}
    Timer {
        id: timer;interval: 200;repeat: true;running: true
        onTriggered: {try {
            ++test.ticks;++test.waited;test.check(test.ticks<600,"UI acceptance timeout at step "+test.step)
            if(test.step===0){
                if(!test.appWindow)return
                if(test.phase==="dock"){
                    test.check(veyra.setPreference("screenshotDir",test.evidence+"/screenshots"),"isolated screenshot directory accepted")
                    test.check(veyra.setPreference("recordDir",test.evidence+"/recordings"),"isolated recording directory accepted")
                    test.check(veyra.setPreference("autoResume",false),"fresh capture playback")
                    veyra.muted=true;test.appWindow.page="min"
                    veyra.openPath(test.media);test.next(10);return
                }
                if(test.phase==="missing"){
                    const option=veyra.fgBackendChoices.find(x=>x.id==="anr")
                    test.check(option&&option.disabled&&option.note.length>0,"missing runtime disables ANR with reason")
                    const before=veyra.fgBackendName;veyra.fgBackendName="anr"
                    test.check(veyra.fgBackendName===before,"missing runtime preserves previous selection")
                    console.log("ANR_UI_MISSING_PASS");timer.stop();Qt.quit();return
                }
                if(test.phase==="restore"){
                    test.check(veyra.fgBackendName==="anr"&&veyra.fgMultiplier===4,"ANR restart settings")
                    console.log("ANR_UI_RESTORE_PASS");timer.stop();Qt.quit();return
                }
                veyra.setPreference("autoResume",false)
                veyra.muted=true;veyra.nrEnabled=false;veyra.srEnabled=false
                test.appWindow.page="pro"
                const page=test.pro(test.appWindow.contentItem);if(page)page.tab="fg"
                const option=veyra.fgBackendChoices.find(x=>x.id==="anr")
                test.check(option&&!option.disabled,"ANR runtime capability and dropdown choice")
                test.check(veyra.addEffect("anr-fg")>=0,"add ANR frame-generation node")
                const selector=test.find(test.appWindow.contentItem,"list-fg-backend")
                test.check(selector,"actual dropdown created");selector.picked("anr")
                test.check(veyra.fgBackendName==="anr","dropdown commits ANR")
                veyra.fgMultiplier=2;veyra.openPath(test.media);test.next(1)
            }else if(test.step===1){
                if(veyra.applying||!veyra.running||veyra.position<0.5||!veyra.fgActive)return
                test.check(veyra.fgActive,"ANR 2X active: "+veyra.statusText)
                test.check(veyra.runStatusDetail.indexOf("Apex ANR")>=0,"actual provider label")
                console.log("ANR_UI_2X_PASS",veyra.runStatusDetail)
                veyra.fgMultiplier=4;test.next(2)
            }else if(test.step===2){
                if(test.waited<12||veyra.applying)return
                test.check(veyra.fgBackendName==="anr"&&veyra.fgMultiplier===4&&veyra.fgActive,"ANR live 4X transaction")
                console.log("ANR_UI_4X_PASS",veyra.runStatusDetail)
                veyra.fgMultiplier=2;veyra.fgBackendName="dlss";test.next(3)
            }else if(test.step===3){
                if(test.waited<12||veyra.applying)return
                test.check(veyra.fgBackendName==="dlss"&&veyra.fgActive,"switch back to original DLSS")
                veyra.fgBackendName="anr";veyra.fgMultiplier=4;test.next(4)
            }else if(test.step===4){
                if(test.waited<12||veyra.applying)return
                test.check(veyra.fgBackendName==="anr"&&veyra.fgMultiplier===4&&veyra.fgActive,"return to ANR")
                test.appWindow.contentItem.grabToImage(result=>result.saveToFile(test.evidence+"/anr-ui.png"))
                test.next(5)
            }else if(test.step===10){
                if(!veyra.running||veyra.position<0.5||veyra.applying)return
                test.check(test.appWindow.page==="min","minimal mode stays active")
                const shot=test.find(test.appWindow.contentItem,"dock-screenshot"),record=test.find(test.appWindow.contentItem,"dock-record")
                test.check(shot&&record&&shot.enabled&&record.enabled,"capture buttons available without Pro mode")
                const windowButton=test.find(test.appWindow.contentItem,"window-min")
                test.check(Math.abs(shot.mapToItem(test.appWindow.contentItem,0,shot.height/2).y-windowButton.mapToItem(test.appWindow.contentItem,0,windowButton.height/2).y)<1,"capture icon aligned to existing dock row")
                test.check(shot.width===32&&shot.height===30&&record.width===32&&record.height===30,"capture icon sizing matches navigation")
                shot.clicked();record.clicked();test.next(11)
            }else if(test.step===11){
                if(!veyra.recording||test.waited<12||!veyra.lastScreenshot)return
                test.firstScreenshot=veyra.lastScreenshot
                test.check(test.find(test.appWindow.contentItem,"dock-record").recording,"recording indicator active")
                test.find(test.appWindow.contentItem,"dock-record").clicked();test.next(12)
            }else if(test.step===12){
                if(test.waited<6||veyra.recording||veyra.recordingState.finishing)return
                veyra.seekTo(1.0);test.appWindow.toggleFullscreen();test.next(13)
            }else if(test.step===13){
                if(test.waited<10||veyra.applying)return
                if(veyra.paused){veyra.togglePlayPause();return}
                if(!veyra.fgActive)return
                test.check(test.appWindow.fullscreen&&test.appWindow.page==="min","fullscreen minimal mode")
                test.check(veyra.fgActive,"ANR continues after seek/fullscreen")
                test.find(test.appWindow.contentItem,"dock-screenshot").clicked()
                test.find(test.appWindow.contentItem,"dock-record").clicked();test.next(14)
            }else if(test.step===14){
                if(!veyra.recording||test.waited<12||!veyra.lastScreenshot||veyra.lastScreenshot===test.firstScreenshot)return
                test.find(test.appWindow.contentItem,"dock-record").clicked()
                test.appWindow.contentItem.grabToImage(result=>result.saveToFile(test.evidence+"/dock-fullscreen.png"))
                test.next(15)
            }else if(test.step===15){
                if(test.waited<6||veyra.recording||veyra.recordingState.finishing)return
                test.appWindow.toggleFullscreen();test.next(16)
            }else if(test.step===16&&test.waited>6){
                test.check(test.appWindow.page==="min","capture never requires Pro mode")
                test.appWindow.contentItem.grabToImage(result=>result.saveToFile(test.evidence+"/dock-minimal.png"))
                console.log("ANR_DOCK_CAPTURE_PASS");timer.stop();Qt.quit()
            }else if(test.step===5&&test.waited>5){
                console.log("ANR_UI_PASS");timer.stop();Qt.quit()
            }
        }catch(e){console.error("ANR_UI_FAIL",e.message);timer.stop();Qt.quit()}}
    }
}
