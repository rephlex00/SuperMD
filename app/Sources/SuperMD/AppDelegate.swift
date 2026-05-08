import AppKit
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Register for drag-and-drop of supernote files onto the dock icon.
        NSAppleEventManager.shared().setEventHandler(
            self,
            andSelector: #selector(handleOpenURL(_:withReplyEvent:)),
            forEventClass: AEEventClass(kInternetEventClass),
            andEventID: AEEventID(kAEGetURL)
        )
    }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        AppModel.shared?.handleDroppedFiles(filenames.map(URL.init(fileURLWithPath:)))
        sender.reply(toOpenOrPrint: .success)
    }

    @objc func handleOpenURL(_ event: NSAppleEventDescriptor, withReplyEvent reply: NSAppleEventDescriptor) {
        guard let urlString = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue,
              let url = URL(string: urlString) else { return }
        // Reserved for a future supermd:// URL scheme.
        _ = url
    }

    func applicationWillTerminate(_ notification: Notification) {
        AppModel.shared?.shutdown()
    }
}
