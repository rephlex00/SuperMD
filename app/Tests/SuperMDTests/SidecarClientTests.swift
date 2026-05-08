import XCTest
@testable import SuperMD

/// We test SidecarClient in isolation by giving it a mock SidecarTransport
/// that records calls and returns canned responses. This proves the typed
/// wrappers translate to the right RPC method names with the right params,
/// and parse results back into the right Swift types.
final class SidecarClientTests: XCTestCase {
    private final class MockTransport: SidecarTransport {
        var calls: [(method: String, params: [String: Any])] = []
        var responses: [String: [String: Any]] = [:]
        var nextError: Error? = nil

        func call(_ method: String, params: [String: Any]) async throws -> [String: Any] {
            calls.append((method, params))
            if let err = nextError { nextError = nil; throw err }
            return responses[method] ?? [:]
        }
    }

    func test_ping_returns_true_when_pong() async throws {
        let mock = MockTransport()
        mock.responses["system.ping"] = ["pong": true, "version": "0.1.0"]
        let client = SidecarClient(); client.transport = mock
        let ok = try await client.ping()
        XCTAssertTrue(ok)
        XCTAssertEqual(mock.calls.first?.method, "system.ping")
    }

    func test_listVaults_parses_array() async throws {
        let mock = MockTransport()
        mock.responses["obsidian.list_vaults"] = [
            "vaults": [
                ["id": "abc", "name": "VaultA", "path": "/v/a", "exists": true],
                ["id": "def", "name": "VaultB", "path": "/v/b", "exists": false],
            ]
        ]
        let client = SidecarClient(); client.transport = mock
        let vaults = try await client.listVaults()
        XCTAssertEqual(vaults.map(\.name), ["VaultA", "VaultB"])
        XCTAssertEqual(vaults.first?.exists, true)
    }

    func test_convertFile_passes_force_and_model() async throws {
        let mock = MockTransport()
        mock.responses["convert.file"] = ["task_id": "conv-12345"]
        let client = SidecarClient(); client.transport = mock
        let id = try await client.convertFile(
            input: "/tmp/a.note",
            output: "/tmp/out",
            model: "claude-3-5-sonnet",
            force: true
        )
        XCTAssertEqual(id, "conv-12345")
        let p = mock.calls.first!.params
        XCTAssertEqual(p["input"] as? String, "/tmp/a.note")
        XCTAssertEqual(p["force"] as? Bool, true)
        XCTAssertEqual(p["model"] as? String, "claude-3-5-sonnet")
    }

    func test_cloudLogin_returns_token_string() async throws {
        let mock = MockTransport()
        mock.responses["cloud.login"] = ["ok": true, "token": "JWT-XYZ"]
        let client = SidecarClient(); client.transport = mock
        let tok = try await client.cloudLogin(email: "a@b.c", password: "pw")
        XCTAssertEqual(tok, "JWT-XYZ")
    }

    func test_propagates_rpc_errors() async {
        let mock = MockTransport()
        mock.nextError = SidecarError.rpc(code: -32011, message: "OTP cancelled")
        let client = SidecarClient(); client.transport = mock
        do {
            _ = try await client.cloudLogin(email: "a@b.c", password: "pw")
            XCTFail("expected error")
        } catch let SidecarError.rpc(code, message) {
            XCTAssertEqual(code, -32011)
            XCTAssertTrue(message.contains("OTP"))
        } catch {
            XCTFail("wrong error type: \(error)")
        }
    }

    func test_ollamaStatus_false_when_running_missing() async throws {
        let mock = MockTransport()
        mock.responses["llm.ollama_status"] = [:]
        let client = SidecarClient(); client.transport = mock
        let running = try await client.ollamaStatus()
        XCTAssertFalse(running)
    }

    func test_listModels_partitions_api_and_ollama() async throws {
        let mock = MockTransport()
        mock.responses["llm.list_models"] = [
            "api": [["id": "gpt-4o-mini", "provider": "openai"]],
            "ollama": [["id": "qwen2.5-vl:7b"]],
        ]
        let client = SidecarClient(); client.transport = mock
        let r = try await client.listModels()
        XCTAssertEqual(r.api.first?.id, "gpt-4o-mini")
        XCTAssertEqual(r.ollama.first?.id, "qwen2.5-vl:7b")
    }
}
