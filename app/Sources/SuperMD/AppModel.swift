import Foundation
import AppKit
import Combine

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

    func start() {
        sidecar.delegate = self
        do {
            try sidecar.start()
            sidecarStatus = .running
        } catch {
            sidecarStatus = .failed(error.localizedDescription)
            return
        }

        Task { await initialProbe() }

        // Persist any setting change.
        $settings
            .dropFirst()
            .debounce(for: .milliseconds(400), scheduler: RunLoop.main)
            .sink { $0.save() }
            .store(in: &cancellables)

        // Start watcher if configured.
        if settings.input.watchInbox, let url = settings.input.inboxURL {
            InboxWatcher.shared.start(at: url) { [weak self] urls in
                self?.handleDroppedFiles(urls)
            }
        }

        // Start cloud sync if configured.
        if settings.input.cloudSyncEnabled, let token = settings.input.cloudToken {
            Task { await reauthenticateCloud(token: token) }
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
        for url in urls where SuperMDFile.isSupported(url) {
            queue.enqueue(input: url, output: settings.output.resolvedRoot)
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
    nonisolated func sidecar(_ manager: SidecarManager, didEmit notification: SidecarNotification) {
        Task { @MainActor in
            switch notification.method {
            case "convert.started":
                queue.handleStarted(notification.params)
            case "convert.page":
                queue.handlePage(notification.params)
            case "convert.finished":
                queue.handleFinished(notification.params)
            case "convert.skipped":
                queue.handleSkipped(notification.params)
            case "convert.failed":
                queue.handleFailed(notification.params)
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
