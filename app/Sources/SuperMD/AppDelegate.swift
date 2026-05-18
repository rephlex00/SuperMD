import AppKit
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // When launched via `swift run` the process inherits a non-regular
        // activation policy, so windows never become key and keystrokes
        // (e.g. ⌘V) leak to whichever app was previously frontmost. Force a
        // regular policy + activate so the dev experience matches the
        // packaged .app.
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

        // Register for drag-and-drop of supernote files onto the dock icon.
        NSAppleEventManager.shared().setEventHandler(
            self,
            andSelector: #selector(handleOpenURL(_:withReplyEvent:)),
            forEventClass: AEEventClass(kInternetEventClass),
            andEventID: AEEventID(kAEGetURL)
        )
    }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        FileHandle.standardError.write(Data("[AppDelegate] openFiles \(filenames.count)\n".utf8))
        guard let app = AppModel.shared, app.settings.input.dragAndDropEnabled else {
            sender.reply(toOpenOrPrint: .cancel)
            return
        }
        app.handleDroppedFiles(filenames.map(URL.init(fileURLWithPath:)))
        sender.reply(toOpenOrPrint: .success)
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        FileHandle.standardError.write(Data("[AppDelegate] open(urls) \(urls.count)\n".utf8))
        guard let app = AppModel.shared, app.settings.input.dragAndDropEnabled else { return }
        app.handleDroppedFiles(urls)
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
