import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        VStack(spacing: 0) {
            HeaderBar()
            SidecarStatusBanner()
            Divider()
            HSplitView {
                JobQueueView()
                    .frame(minWidth: 360)
                LogTailView()
                    .frame(minWidth: 280)
            }
        }
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            guard app.settings.input.dragAndDropEnabled else { return false }
            return handleDrop(providers: providers)
        }
        .sheet(item: $app.pendingOTP) { otp in
            CloudOTPSheet(email: otp.email)
        }
        .sheet(isPresented: $app.showAbout) { AboutSheet() }
    }

    private func handleDrop(providers: [NSItemProvider]) -> Bool {
        FileHandle.standardError.write(Data("[Drop] received \(providers.count) providers\n".utf8))
        let lock = NSLock()
        var urls: [URL] = []
        let group = DispatchGroup()
        for p in providers {
            group.enter()
            _ = p.loadDataRepresentation(forTypeIdentifier: UTType.fileURL.identifier) { data, error in
                defer { group.leave() }
                if let error {
                    FileHandle.standardError.write(Data("[Drop] load error: \(error)\n".utf8))
                    return
                }
                guard let data,
                      let url = URL(dataRepresentation: data, relativeTo: nil, isAbsolute: true) else {
                    FileHandle.standardError.write(Data("[Drop] no URL from data (\(data?.count ?? 0) bytes)\n".utf8))
                    return
                }
                lock.lock(); urls.append(url); lock.unlock()
            }
        }
        group.notify(queue: .main) {
            FileHandle.standardError.write(Data("[Drop] dispatching \(urls.count) urls to handleDroppedFiles\n".utf8))
            app.handleDroppedFiles(urls)
        }
        return true
    }
}

private struct SidecarStatusBanner: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        switch app.sidecarStatus {
        case .running:
            EmptyView()
        case .stopped:
            banner(systemImage: "exclamationmark.triangle.fill",
                   text: "Sidecar stopped.",
                   tint: .orange)
        case .failed(let reason):
            banner(systemImage: "exclamationmark.octagon.fill",
                   text: "Sidecar failed: \(reason).",
                   tint: .red)
        }
    }

    private func banner(systemImage: String, text: String, tint: Color) -> some View {
        HStack {
            Image(systemName: systemImage).foregroundStyle(tint)
            Text(text).font(.callout)
            Spacer()
            Button("Restart Sidecar") { app.restartSidecar() }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 6)
        .background(tint.opacity(0.12))
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
            SettingsLink {
                Image(systemName: "gearshape")
            }
            .buttonStyle(.borderless)
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

private struct AboutSheet: View {
    @EnvironmentObject var app: AppModel
    @Environment(\.dismiss) private var dismiss

    private var version: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?"
    }

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "tray.full.fill")
                .font(.system(size: 48))
                .foregroundStyle(.tint)
            Text("SuperMD").font(.title)
            Text("Version \(version)").foregroundStyle(.secondary)
            Text("Supernote notes → Markdown via LLM transcription.")
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            HStack {
                Link("Source", destination: URL(string: "https://github.com/anthropics/SuperMD")!)
                Text("•")
                Link("Issues", destination: URL(string: "https://github.com/anthropics/SuperMD/issues")!)
            }
            .font(.callout)
            Button("Done") { dismiss() }
                .keyboardShortcut(.defaultAction)
        }
        .padding(28)
        .frame(width: 340)
    }
}
