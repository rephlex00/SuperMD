import Foundation

/// Spawns and manages the lifetime of the Python sidecar process. Provides a
/// typed `SidecarClient` for making JSON-RPC calls and forwards
/// server-initiated notifications to its delegate.
///
/// The sidecar binary is expected at `Contents/Resources/supermd-sidecar`
/// inside the .app bundle. In dev mode (running from `swift run`), the manager
/// falls back to `python -m supermd_sidecar` from the repo root.
final class SidecarManager {
    weak var delegate: SidecarManagerDelegate?
    private var process: Process?
    private var stdin: FileHandle?
    private var stdoutPipe: Pipe?
    private var stderrPipe: Pipe?
    private var lineBuffer = LineBuffer()

    private let writeQueue = DispatchQueue(label: "supermd.sidecar.write")
    private var pending: [Int: CheckedContinuation<[String: Any], Error>] = [:]
    private let pendingLock = NSLock()
    private var nextID: Int = 0

    let client: SidecarClient

    init() {
        self.client = SidecarClient()
        client.transport = self
    }

    func start() throws {
        FileHandle.standardError.write(Data("[SidecarManager] start() entry\n".utf8))
        let process = Process()
        let stdin = Pipe()
        let stdout = Pipe()
        let stderr = Pipe()
        process.standardInput = stdin
        process.standardOutput = stdout
        process.standardError = stderr

        let bundled = Bundle.main.url(forResource: "supermd-sidecar", withExtension: nil)
        if let bundled, FileManager.default.isExecutableFile(atPath: bundled.path) {
            process.executableURL = bundled
        } else {
            // Dev fallback: prefer the project's uv-managed venv if present, else
            // fall back to the system python3 with PYTHONPATH set.
            let repoRoot = Self.devRepoRoot()
            let venvPython = repoRoot.appendingPathComponent(".venv/bin/python3")
            if FileManager.default.isExecutableFile(atPath: venvPython.path) {
                process.executableURL = venvPython
                process.arguments = ["-m", "supermd_sidecar"]
            } else {
                process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
                process.arguments = ["python3", "-m", "supermd_sidecar"]
            }
            var env = ProcessInfo.processInfo.environment
            env["PYTHONPATH"] = [
                repoRoot.appendingPathComponent("sidecar/src").path,
                repoRoot.appendingPathComponent("src").path,
                env["PYTHONPATH"] ?? "",
            ].joined(separator: ":")
            env["PYTHONUNBUFFERED"] = "1"
            process.environment = env
        }

        let exe = process.executableURL?.path ?? "<nil>"
        let args = (process.arguments ?? []).joined(separator: " ")
        FileHandle.standardError.write(Data("[SidecarManager] launching: \(exe) \(args)\n".utf8))
        try process.run()
        FileHandle.standardError.write(Data("[SidecarManager] process.run() ok, pid=\(process.processIdentifier)\n".utf8))

        self.process = process
        self.stdin = stdin.fileHandleForWriting
        self.stdoutPipe = stdout
        self.stderrPipe = stderr

        stdout.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            self?.lineBuffer.append(data) { line in
                self?.handleIncoming(line: line)
            }
        }

        stderr.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty, let s = String(data: data, encoding: .utf8) else { return }
            FileHandle.standardError.write(data)
            _ = s
        }
    }

    func shutdown() {
        Task { try? await client.shutdown() }
        // Give the sidecar 250ms to exit cleanly, then force-kill.
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.25) { [weak self] in
            self?.process?.terminate()
        }
    }

    // MARK: - Transport

    fileprivate func send(method: String, params: [String: Any]) async throws -> [String: Any] {
        let id: Int
        pendingLock.lock()
        nextID += 1
        id = nextID
        pendingLock.unlock()

        let payload: [String: Any] = [
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        ]

        return try await withCheckedThrowingContinuation { cont in
            pendingLock.lock()
            pending[id] = cont
            pendingLock.unlock()

            writeQueue.async {
                do {
                    guard let stdin = self.stdin else {
                        throw SidecarError.notRunning
                    }
                    let data = try JSONSerialization.data(withJSONObject: payload)
                    var line = data
                    line.append(0x0A)  // '\n'
                    try stdin.write(contentsOf: line)
                } catch {
                    self.pendingLock.lock()
                    let cont = self.pending.removeValue(forKey: id)
                    self.pendingLock.unlock()
                    cont?.resume(throwing: error)
                }
            }
        }
    }

    private func handleIncoming(line: Data) {
        guard let obj = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { return }

        if let id = obj["id"] as? Int {
            pendingLock.lock()
            let cont = pending.removeValue(forKey: id)
            pendingLock.unlock()
            if let result = obj["result"] as? [String: Any] {
                cont?.resume(returning: result)
            } else if let err = obj["error"] as? [String: Any] {
                let message = err["message"] as? String ?? "rpc error"
                let code = err["code"] as? Int ?? -1
                cont?.resume(throwing: SidecarError.rpc(code: code, message: message))
            } else {
                cont?.resume(returning: [:])
            }
            return
        }

        // No id → server-initiated notification
        if let method = obj["method"] as? String {
            let params = (obj["params"] as? [String: Any]) ?? [:]
            delegate?.sidecar(self, didEmit: SidecarNotification(method: method, params: params))
        }
    }

    private static func devRepoRoot() -> URL {
        // Allow an explicit override (set by dev launchers / make dev).
        if let override = ProcessInfo.processInfo.environment["SUPERMD_REPO_ROOT"] {
            return URL(fileURLWithPath: override)
        }
        let fm = FileManager.default
        // Walk up from the executable looking for a sentinel that uniquely
        // identifies the project root: either `app/Package.swift` (running
        // from a bundled .app or copy outside the build tree) or `Package.swift`
        // alongside an `Sources/SuperMD/` (running from inside `app/.build/`).
        let seeds = [
            URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent(),
            URL(fileURLWithPath: fm.currentDirectoryPath),
        ]
        for seed in seeds {
            var dir = seed
            for _ in 0..<10 {
                if fm.fileExists(atPath: dir.appendingPathComponent("app/Package.swift").path) {
                    return dir
                }
                if fm.fileExists(atPath: dir.appendingPathComponent("Package.swift").path)
                    && fm.fileExists(atPath: dir.appendingPathComponent("Sources/SuperMD").path) {
                    return dir.deletingLastPathComponent()
                }
                dir.deleteLastPathComponent()
            }
        }
        return URL(fileURLWithPath: fm.currentDirectoryPath)
    }
}

protocol SidecarManagerDelegate: AnyObject {
    func sidecar(_ manager: SidecarManager, didEmit notification: SidecarNotification)
}

struct SidecarNotification {
    let method: String
    let params: [String: Any]
}

enum SidecarError: Error, LocalizedError {
    case rpc(code: Int, message: String)
    case notRunning
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .rpc(let code, let message): return "RPC \(code): \(message)"
        case .notRunning: return "Sidecar is not running"
        case .decoding(let s): return "Decoding error: \(s)"
        }
    }
}

// Bridge for the typed client.
extension SidecarManager: SidecarTransport {
    func call(_ method: String, params: [String: Any]) async throws -> [String: Any] {
        try await send(method: method, params: params)
    }
}

protocol SidecarTransport: AnyObject {
    func call(_ method: String, params: [String: Any]) async throws -> [String: Any]
}
