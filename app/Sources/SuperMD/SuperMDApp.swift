import SwiftUI

@main
struct SuperMDApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var appModel = AppModel()

    var body: some Scene {
        WindowGroup("SuperMD") {
            ContentView()
                .environmentObject(appModel)
                .frame(minWidth: 720, minHeight: 480)
                .onAppear { appModel.start() }
        }
        .commands {
            CommandGroup(replacing: .appInfo) {
                Button("About SuperMD") { appModel.showAbout = true }
            }
            CommandGroup(after: .appSettings) {
                Button("Force Reprocess Selected") {
                    appModel.forceReprocessSelection()
                }
                .keyboardShortcut("r", modifiers: [.command, .shift])
            }
            CommandMenu("Conversion") {
                Button(appModel.queue.isPaused ? "Resume" : "Pause") {
                    appModel.queue.togglePause()
                }
                .keyboardShortcut(" ", modifiers: [])
                Divider()
                Button("Open Inbox in Finder") { appModel.revealInbox() }
                Button("Open Output in Finder") { appModel.revealOutput() }
            }
        }

        Settings {
            SettingsView()
                .environmentObject(appModel)
                .frame(width: 720, height: 520)
        }

        MenuBarExtra("SuperMD", systemImage: appModel.menuBarSymbol) {
            MenuBarContent()
                .environmentObject(appModel)
        }
        .menuBarExtraStyle(.window)
    }
}
