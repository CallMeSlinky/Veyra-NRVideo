// Acceptance-only: inspect the real translated mode-switch dialog.
import QtQuick
Item {
    id: probe
    property var appWindow: Window.window
    property string screenshot: ""
    property int ticks: 0
    function find(item, name) {
        if (item.objectName === name) return item
        for (const child of item.children || []) { const match = find(child, name); if (match) return match }
        return null
    }
    function check(ok, why) { if (!ok) throw new Error(why) }
    Timer {
        interval: 150; repeat: true; running: true
        onTriggered: { try {
            if (!probe.appWindow) return
            ++probe.ticks
            if (probe.ticks === 1) {
                veyra.setPreference("language", "en")
                probe.appWindow.page = "pro"
                const dialog = probe.find(probe.appWindow.contentItem, "node-switch-dialog")
                probe.check(dialog, "mode-switch dialog exists")
                dialog.targetMode = 1; dialog.open()
            }
            if (probe.ticks < 5) return
            for (const mode of ["list", "nodes"]) {
                const badge = probe.find(probe.appWindow.contentItem, "mode-switch-" + mode + "-tag")
                probe.check(badge && badge.visible && badge.width > 100, "badge is visible: " + mode)
                const text = badge.children.find(child => child.text === badge.text && child.contentWidth !== undefined)
                probe.check(text && text.contentWidth <= text.width + 1, "badge text fits horizontally: " + mode)
                probe.check(text.contentHeight <= badge.height - 5, "badge grows to fit all lines: " + mode)
                const card = badge.parent.parent
                const corner = badge.mapToItem(card, badge.width, badge.height)
                probe.check(corner.x <= card.width - 11 && corner.y <= card.height - 11, "badge stays inside card: " + mode)
                if (mode === "nodes") probe.check(text.lineCount > 1, "long English message wraps")
            }
            stop()
            probe.appWindow.contentItem.grabToImage(result => {
                if (!result.saveToFile(probe.screenshot)) console.log("MODE_DIALOG_FAIL screenshot")
                else console.log("MODE_DIALOG_PASS", probe.screenshot)
                Qt.quit()
            })
        } catch (error) {
            console.log("MODE_DIALOG_FAIL", String(error)); stop(); Qt.quit()
        } }
    }
}
