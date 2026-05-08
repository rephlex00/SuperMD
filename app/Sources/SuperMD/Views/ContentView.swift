import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        VStack(spacing: 0) {
            HeaderBar()
            Divider()
            HSplitView {
                JobQueueView()
                    .frame(minWidth: 360)
                LogTailView()
                    .frame(minWidth: 280)
            }
        }
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            handleDrop(providers: providers)
        }
        .sheet(item: $app.pendingOTP) { otp in
            CloudOTPSheet(email: otp.email)
        }
    }

    private func handleDrop(providers: [NSItemProvider]) -> Bool {
        var urls: [URL] = []
        let group = DispatchGroup()
        for p in providers {
            group.enter()
            _ = p.loadObject(ofClass: URL.self) { url, _ in
                if let url { urls.append(url) }
                group.leave()
            }
        }
        group.notify(queue: .main) {
            app.handleDroppedFiles(urls)
        }
        return true
    }
}

private struct HeaderBar: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "tray.full.fill")
            VStack(alignment: .leading, spacing: 2) {
                Text("SuperMD").font(.headline)
                statusLine
            }
            Spacer()
            Button(action: { app.queue.togglePause() }) {
                Image(systemName: app.queue.isPaused ? "play.fill" : "pause.fill")
            }
            .help(app.queue.isPaused ? "Resume" : "Pause")
            Button(action: { NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil) }) {
                Image(systemName: "gearshape")
            }
            .help("Settings")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    @ViewBuilder
    private var statusLine: some View {
        switch app.cloudStatus {
        case .signedOut:
            Text("Sign in to Supernote Cloud in Settings • Drop files to convert")
                .font(.caption).foregroundStyle(.secondary)
        case .signedIn(let email):
            Text("Cloud: \(email)").font(.caption).foregroundStyle(.secondary)
        case .syncing(let n):
            Text("Cloud sync: \(n) downloaded").font(.caption).foregroundStyle(.secondary)
        case .awaitingOTP:
            Text("Awaiting verification code").font(.caption).foregroundStyle(.orange)
        case .tokenExpired:
            Text("Cloud token expired — sign in again").font(.caption).foregroundStyle(.red)
        case .error(let s):
            Text("Cloud error: \(s)").font(.caption).foregroundStyle(.red)
        }
    }
}
