import SwiftUI

struct LogTailView: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Log").font(.subheadline).foregroundStyle(.secondary)
                Spacer()
                Button("Open log file") {
                    Task {
                        if let path = try? await app.sidecar.client.configPath().logDir {
                            NSWorkspace.shared.open(URL(fileURLWithPath: path))
                        }
                    }
                }
                .buttonStyle(.borderless)
                .font(.caption)
            }
            .padding(.horizontal, 12).padding(.top, 10).padding(.bottom, 6)

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(app.logTail) { line in
                            LogLineView(line: line).id(line.id)
                        }
                    }
                    .padding(.horizontal, 8)
                }
                .onChange(of: app.logTail.count) {
                    if let last = app.logTail.last {
                        withAnimation(.linear(duration: 0.1)) { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }
        }
    }
}

private struct LogLineView: View {
    let line: LogLine
    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Text(line.level)
                .font(.system(.caption2, design: .monospaced))
                .foregroundStyle(color)
                .frame(width: 38, alignment: .leading)
            Text(line.message)
                .font(.system(.caption, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
    private var color: Color {
        switch line.level {
        case "ERROR", "CRITICAL": return .red
        case "WARN", "WARNING": return .orange
        case "DEBUG": return .gray
        default: return .blue
        }
    }
}

struct MenuBarContent: View {
    @EnvironmentObject var app: AppModel
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: app.menuBarSymbol)
                Text("SuperMD")
                Spacer()
            }
            Divider()
            Button(app.queue.isPaused ? "Resume conversion" : "Pause conversion") {
                app.queue.togglePause()
            }
            Button("Open SuperMD") {
                NSApp.activate(ignoringOtherApps: true)
                NSApp.windows.first?.makeKeyAndOrderFront(nil)
            }
            Divider()
            Button("Quit") { NSApp.terminate(nil) }
        }
        .padding(10)
        .frame(width: 240)
    }
}

struct CloudOTPSheet: View {
    @EnvironmentObject var app: AppModel
    @Environment(\.dismiss) private var dismiss
    let email: String
    @State private var code: String = ""
    @State private var submitting = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Verify your Supernote account").font(.headline)
            Text("A 6-digit code was emailed to \(email).")
                .font(.callout).foregroundStyle(.secondary)
            TextField("Verification code", text: $code)
                .textFieldStyle(.roundedBorder)
                .frame(width: 220)
            if let error {
                Text(error).font(.caption).foregroundStyle(.red)
            }
            HStack {
                Button("Cancel") { dismiss(); app.pendingOTP = nil }
                Spacer()
                Button(submitting ? "Verifying…" : "Verify") {
                    submit()
                }
                .keyboardShortcut(.return)
                .disabled(submitting || code.count < 4)
            }
        }
        .padding(20)
        .frame(width: 380)
    }

    private func submit() {
        submitting = true
        error = nil
        Task {
            do {
                try await app.sidecar.client.cloudSubmitOTP(code: code)
                app.pendingOTP = nil
                dismiss()
            } catch {
                self.error = error.localizedDescription
            }
            submitting = false
        }
    }
}
