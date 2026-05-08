import Foundation

/// Typed wrapper around the JSON-RPC transport. Each method maps 1-to-1 to an
/// entry in `sidecar/PROTOCOL.md`.
final class SidecarClient {
    weak var transport: SidecarTransport?

    // MARK: - System

    func ping() async throws -> Bool {
        let r = try await call("system.ping", params: [:])
        return (r["pong"] as? Bool) ?? false
    }

    func shutdown() async throws {
        _ = try await call("system.shutdown", params: [:])
    }

    func configPath() async throws -> ConfigPaths {
        let r = try await call("system.config_path", params: [:])
        return ConfigPaths(
            configPath: r["config_path"] as? String ?? "",
            configDir: r["config_dir"] as? String ?? "",
            logDir: r["log_dir"] as? String ?? "",
            metadataDB: r["metadata_db"] as? String ?? ""
        )
    }

    // MARK: - LLM

    struct ListModelsResult { let api: [LLMModel]; let ollama: [LLMModel] }

    func listModels() async throws -> ListModelsResult {
        let r = try await call("llm.list_models", params: [:])
        return ListModelsResult(
            api: parseModels(r["api"]),
            ollama: parseModels(r["ollama"])
        )
    }

    func setLLMKey(provider: String, key: String) async throws {
        _ = try await call("llm.set_key", params: ["provider": provider, "key": key])
    }

    func testLLMKey(provider: String, key: String) async throws {
        _ = try await call("llm.test_key", params: ["provider": provider, "key": key])
    }

    func ollamaStatus() async throws -> Bool {
        let r = try await call("llm.ollama_status", params: [:])
        return (r["running"] as? Bool) ?? false
    }

    // MARK: - Obsidian

    func listVaults() async throws -> [ObsidianVault] {
        let r = try await call("obsidian.list_vaults", params: [:])
        let raw = (r["vaults"] as? [[String: Any]]) ?? []
        return raw.map {
            ObsidianVault(
                id: $0["id"] as? String ?? UUID().uuidString,
                name: $0["name"] as? String ?? "",
                path: $0["path"] as? String ?? "",
                exists: $0["exists"] as? Bool ?? false
            )
        }
    }

    func openNote(vault: String, file: String) async throws {
        _ = try await call("obsidian.open_note", params: ["vault": vault, "file": file])
    }

    func startHeadlessObsidian(vaultPath: String) async throws -> Int {
        let r = try await call("obsidian.start_headless", params: ["vault_path": vaultPath])
        return (r["pid"] as? Int) ?? -1
    }

    func stopHeadlessObsidian() async throws {
        _ = try await call("obsidian.stop_headless", params: [:])
    }

    // MARK: - Cloud

    func cloudLogin(email: String, password: String) async throws -> String {
        let r = try await call("cloud.login", params: ["email": email, "password": password])
        return (r["token"] as? String) ?? ""
    }

    func cloudLoginToken(token: String) async throws {
        _ = try await call("cloud.login_token", params: ["token": token])
    }

    func cloudSubmitOTP(code: String) async throws {
        _ = try await call("cloud.submit_otp", params: ["code": code])
    }

    func cloudStartSync(remotePath: String, localPath: String, intervalSec: Int) async throws -> String {
        let r = try await call("cloud.start_sync", params: [
            "remote_path": remotePath,
            "local_path": localPath,
            "interval_sec": intervalSec,
        ])
        return (r["task_id"] as? String) ?? ""
    }

    func cloudStopSync(taskID: String) async throws {
        _ = try await call("cloud.stop_sync", params: ["task_id": taskID])
    }

    func cloudLogout() async throws {
        _ = try await call("cloud.logout", params: [:])
    }

    // MARK: - Convert

    func convertFile(input: String, output: String, model: String? = nil,
                     force: Bool = false, config: [String: Any] = [:]) async throws -> String {
        var params: [String: Any] = ["input": input, "output": output, "force": force, "config": config]
        if let model { params["model"] = model }
        let r = try await call("convert.file", params: params)
        return (r["task_id"] as? String) ?? ""
    }

    func convertDirectory(input: String, output: String, model: String? = nil,
                          force: Bool = false, config: [String: Any] = [:]) async throws -> [String] {
        var params: [String: Any] = ["input": input, "output": output, "force": force, "config": config]
        if let model { params["model"] = model }
        let r = try await call("convert.directory", params: params)
        return (r["task_ids"] as? [String]) ?? []
    }

    // MARK: - Config

    func readConfig() async throws -> (yaml: String, exists: Bool) {
        let r = try await call("config.read", params: [:])
        return (r["yaml"] as? String ?? "", r["exists"] as? Bool ?? false)
    }

    func writeConfig(yaml: String) async throws {
        _ = try await call("config.write", params: ["yaml": yaml])
    }

    // MARK: - Internal

    private func call(_ method: String, params: [String: Any]) async throws -> [String: Any] {
        guard let transport else { throw SidecarError.notRunning }
        return try await transport.call(method, params: params)
    }

    private func parseModels(_ raw: Any?) -> [LLMModel] {
        guard let arr = raw as? [[String: Any]] else { return [] }
        return arr.map {
            LLMModel(
                id: $0["id"] as? String ?? "",
                provider: $0["provider"] as? String,
                size: $0["size"] as? Int64
            )
        }
    }
}

struct ConfigPaths {
    let configPath: String
    let configDir: String
    let logDir: String
    let metadataDB: String
}
