import Foundation
import AppKit
import Combine
import ServiceManagement

/// Top-level app state. Owns the SidecarManager, the conversion queue, and
/// the user's settings. SwiftUI views observe this via `@EnvironmentObject`.
@MainActor
final class AppModel: ObservableObject {
    static private(set) weak var shared: AppModel?

    @Published var settings: AppSettings
    @Published var queue: ConversionQueueModel
    @Published var sidecarStatus: SidecarStatus = .stopped
    @Published var cloudStatus: CloudStatus = .signedOut
    @Published var llmAvailability: LLMAvailability = .unknown
    @Published var pendingOTP: PendingOTP? = nil
    @Published var showAbout: Bool = false
    @Published var logTail: [LogLine] = []

    let sidecar: SidecarManager
    private var cancellables = Set<AnyCancellable>()

    init() {
        let settings = AppSettings.load()
        self.settings = settings
        self.queue = ConversionQueueModel()
        self.sidecar = SidecarManager()
        AppModel.shared = self
    }

    private var didStart = false

    func start() {
        FileHandle.standardError.write(Data("[AppModel] start() called (didStart=\(didStart))\n".utf8))
        if didStart { return }
        didStart = true
        sidecar.delegate = self
        do {
            try sidecar.start()
            FileHandle.standardError.write(Data("[AppModel] sidecar.start() returned cleanly\n".utf8))
            sidecarStatus = .running
        } catch {
            let msg = "[AppModel] sidecar.start() threw: \(error)\n"
            FileHandle.standardError.write(Data(msg.utf8))
            sidecarStatus = .failed(error.localizedDescription)
            return
        }

        Task { await initialProbe() }

        // Forward nested ObservableObjects' change events to ours so SwiftUI
        // views observing AppModel re-render when queue.rows / settings.output
        // / etc. mutate.
        queue.objectWillChange
            .sink { [weak self] in self?.objectWillChange.send() }
            .store(in: &cancellables)
        settings.objectWillChange
            .sink { [weak self] in self?.objectWillChange.send() }
            .store(in: &cancellables)

        // Persist any setting change.
        $settings
            .dropFirst()
            .debounce(for: .milliseconds(400), scheduler: RunLoop.main)
            .sink { $0.save() }
            .store(in: &cancellables)

        applyEffectfulSettings()

        // Start watcher if configured. Pushed off main because the first
        // createDirectory(~/Documents/...) can trigger a Documents-folder
        // permission prompt that synchronously blocks the main thread —
        // which means the main window never appears until the user clicks
        // Allow on an invisible dialog.
        let suppressWatcher = ProcessInfo.processInfo.environment["SUPERMD_TEST_NO_INBOX"] != nil
        if settings.input.watchInbox, !suppressWatcher, let url = settings.input.inboxURL {
            DispatchQueue.global(qos: .utility).async { [weak self] in
                InboxWatcher.shared.start(at: url) { urls in
                    Task { @MainActor in self?.handleDroppedFiles(urls) }
                }
            }
        }

        // Start cloud sync if configured.
        if settings.input.cloudSyncEnabled, let token = settings.input.cloudToken {
            Task { await reauthenticateCloud(token: token) }
        }

        // Test hook: SUPERMD_TEST_OUTPUT="/path" overrides output settings
        // for headless drop tests.
        if let outPath = ProcessInfo.processInfo.environment["SUPERMD_TEST_OUTPUT"], !outPath.isEmpty {
            settings.output.mode = .folder
            settings.output.genericOutputPath = outPath
            FileHandle.standardError.write(Data("[AppModel] TEST_OUTPUT override: \(outPath)\n".utf8))
        }

        // Test hook: SUPERMD_TEST_DROP="/path/a.note,/path/b.note" injects a
        // synthetic drop ~2s after launch so automated tests don't need
        // synthetic mouse events.
        if let dropList = ProcessInfo.processInfo.environment["SUPERMD_TEST_DROP"], !dropList.isEmpty {
            let urls = dropList.split(separator: ",").map { URL(fileURLWithPath: String($0)) }
            FileHandle.standardError.write(Data("[AppModel] TEST_DROP scheduling \(urls.count) urls\n".utf8))
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                self.handleDroppedFiles(urls)
            }
        }
    }

    var menuBarSymbol: String {
        switch sidecarStatus {
        case .running:
            return queue.isPaused ? "pause.circle" : "tray.full"
        case .stopped, .failed:
            return "exclamationmark.triangle"
        }
    }

    // MARK: - Drop / convert

    func handleDroppedFiles(_ urls: [URL]) {
        for url in urls {
            let resolved = url.resolvingSymlinksInPath()
            let supported = SuperMDFile.isSupported(resolved)
            FileHandle.standardError.write(Data(
                "[handleDroppedFiles] url=\(url.path) resolved=\(resolved.path) ext=\(resolved.pathExtension) supported=\(supported)\n".utf8
            ))
            if !supported {
                queue.recordUnsupported(input: resolved)
                continue
            }
            queue.enqueue(input: resolved, output: settings.output.resolvedRoot)
        }
    }

    func revealInbox() {
        if let url = settings.input.inboxURL {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        }
    }

    func revealOutput() {
        if let url = settings.output.resolvedRoot {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        }
    }

    func forceReprocessSelection() {
        queue.reprocessSelected()
    }

    private func applyEffectfulSettings() {
        // Activation policy: regular (with dock) vs accessory (menu-bar only).
        let target: NSApplication.ActivationPolicy =
            settings.advanced.hideFromDock ? .accessory : .regular
        if NSApp.activationPolicy() != target {
            NSApp.setActivationPolicy(target)
        }

        // Open at login. SMAppService requires macOS 13+; silent on older OS
        // or unsigned dev builds where registration is rejected.
        if #available(macOS 13.0, *) {
            let svc = SMAppService.mainApp
            let want = settings.advanced.runAtLogin
            do {
                switch (want, svc.status) {
                case (true, .notRegistered), (true, .notFound):
                    try svc.register()
                case (false, .enabled), (false, .requiresApproval):
                    try svc.unregister()
                default:
                    break
                }
            } catch {
                FileHandle.standardError.write(Data(
                    "[AppModel] SMAppService toggle failed: \(error)\n".utf8))
            }
        }
    }

    fileprivate func inputFileName(forTaskID taskID: String?) -> String {
        guard let taskID,
              let row = queue.rows.first(where: { $0.sidecarTaskID == taskID })
        else { return "(unknown)" }
        return row.input.lastPathComponent
    }

    // MARK: - Initial probe

    private func initialProbe() async {
        async let llm: () = probeLLM()
        async let cloud: () = probeCloud()
        async let vaults: () = refreshObsidianVaults()
        _ = await (llm, cloud, vaults)
    }

    private func probeLLM() async {
        do {
            let result = try await sidecar.client.listModels()
            llmAvailability = .available(api: result.api, ollama: result.ollama)
        } catch {
            llmAvailability = .error(error.localizedDescription)
        }
    }

    private func probeCloud() async {
        guard let token = settings.input.cloudToken else { return }
        await reauthenticateCloud(token: token)
    }

    private func refreshObsidianVaults() async {
        do {
            let vaults = try await sidecar.client.listVaults()
            settings.output.discoveredVaults = vaults
        } catch {
            // ignore
        }
    }

    private func reauthenticateCloud(token: String) async {
        do {
            try await sidecar.client.cloudLoginToken(token: token)
            cloudStatus = .signedIn(email: settings.input.cloudEmail ?? "")
        } catch {
            cloudStatus = .tokenExpired
        }
    }

    // MARK: - Shutdown

    func shutdown() {
        sidecar.shutdown()
    }
}

// MARK: - SidecarManagerDelegate

extension AppModel: SidecarManagerDelegate {
    nonisolated func sidecarDidExit(_ manager: SidecarManager, status: Int32) {
        Task { @MainActor in
            sidecarStatus = .failed("Sidecar exited (rc=\(status))")
            for i in queue.rows.indices where queue.rows[i].status == .queued || queue.rows[i].status == .running {
                queue.rows[i].status = .failed
                queue.rows[i].error = "Sidecar exited"
            }
        }
    }

    nonisolated func sidecar(_ manager: SidecarManager, didEmit notification: SidecarNotification) {
        Task { @MainActor in
            switch notification.method {
            case "convert.started":
                queue.handleStarted(notification.params)
            case "convert.page":
                queue.handlePage(notification.params)
            case "convert.finished":
                queue.handleFinished(notification.params)
                if settings.advanced.notificationsOnSuccess {
                    let file = inputFileName(forTaskID: notification.params["task_id"] as? String)
                    Notifier.notify(title: "SuperMD: converted", body: file)
                }
                if settings.output.openInObsidianAfter,
                   settings.output.mode == .vault || settings.output.mode == .headless,
                   let vaultID = settings.output.selectedVaultID,
                   let outputPath = notification.params["output_path"] as? String,
                   let vaultRoot = settings.output.selectedVaultPath {
                    // obsidian.open_note expects a path relative to the vault.
                    let rel = (outputPath as NSString).abbreviatingWithTildeInPath
                    let vaultURL = URL(fileURLWithPath: (vaultRoot as NSString).expandingTildeInPath)
                    let outURL = URL(fileURLWithPath: outputPath)
                    let relPath: String
                    if outURL.path.hasPrefix(vaultURL.path) {
                        relPath = String(outURL.path.dropFirst(vaultURL.path.count + 1))
                    } else {
                        relPath = rel
                    }
                    Task {
                        try? await sidecar.client.openNote(vault: vaultID, file: relPath)
                    }
                }
            case "convert.skipped":
                queue.handleSkipped(notification.params)
            case "convert.failed":
                queue.handleFailed(notification.params)
                if settings.advanced.notificationsOnFailure,
                   (notification.params["error"] as? String) != "cancelled" {
                    let file = inputFileName(forTaskID: notification.params["task_id"] as? String)
                    let err = notification.params["error"] as? String ?? "unknown error"
                    Notifier.notify(title: "SuperMD: failed — \(file)", body: err)
                }
            case "cloud.otp_required":
                pendingOTP = PendingOTP(email: notification.params["email"] as? String ?? "")
            case "cloud.token_refreshed":
                if let token = notification.params["token"] as? String {
                    settings.input.cloudToken = token
                }
            case "cloud.sync_progress":
                cloudStatus = .syncing(downloaded: notification.params["downloaded"] as? Int ?? 0)
            case "log.line":
                let level = notification.params["level"] as? String ?? "INFO"
                let msg = notification.params["msg"] as? String ?? ""
                logTail.append(LogLine(level: level, message: msg))
                if logTail.count > 200 { logTail.removeFirst(logTail.count - 200) }
            default:
                break
            }
        }
    }
}

// MARK: - Status enums

enum SidecarStatus: Equatable {
    case stopped
    case running
    case failed(String)
}

enum CloudStatus: Equatable {
    case signedOut
    case signedIn(email: String)
    case awaitingOTP(email: String)
    case syncing(downloaded: Int)
    case tokenExpired
    case error(String)
}

enum LLMAvailability {
    case unknown
    case available(api: [LLMModel], ollama: [LLMModel])
    case error(String)
}

struct PendingOTP: Identifiable, Equatable {
    let id = UUID()
    let email: String
}

struct LogLine: Identifiable {
    let id = UUID()
    let level: String
    let message: String
}
