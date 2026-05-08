import XCTest
@testable import SuperMD

final class AppSettingsTests: XCTestCase {
    func test_round_trips_through_userdefaults() throws {
        let key = "com.supermd.app.settings.v1"
        UserDefaults.standard.removeObject(forKey: key)

        let s = AppSettings()
        s.input.cloudEmail = "alice@example.com"
        s.input.cloudRemotePath = "/Note/Journal"
        s.output.mode = .vault
        s.output.subfolderInVault = "FromSupernote"
        s.templates.bodyTemplate = "## My template\n\n{{llm_output}}"
        s.save()

        let loaded = AppSettings.load()
        XCTAssertEqual(loaded.input.cloudEmail, "alice@example.com")
        XCTAssertEqual(loaded.input.cloudRemotePath, "/Note/Journal")
        XCTAssertEqual(loaded.output.mode, .vault)
        XCTAssertEqual(loaded.output.subfolderInVault, "FromSupernote")
        XCTAssertEqual(loaded.templates.bodyTemplate, "## My template\n\n{{llm_output}}")
    }

    func test_resolved_root_for_vault_mode_appends_subfolder() {
        let s = AppSettings()
        s.output.mode = .vault
        s.output.selectedVaultPath = "/Users/alice/Vault"
        s.output.subfolderInVault = "Supernote"
        XCTAssertEqual(s.output.resolvedRoot?.path, "/Users/alice/Vault/Supernote")
    }

    func test_resolved_root_for_folder_mode_uses_generic_path() {
        let s = AppSettings()
        s.output.mode = .folder
        s.output.genericOutputPath = "/tmp/md-output"
        XCTAssertEqual(s.output.resolvedRoot?.path, "/tmp/md-output")
    }

    func test_inboxURL_expands_tilde() {
        let s = AppSettings()
        s.input.inboxPath = "~/Documents/Foo"
        let url = s.input.inboxURL
        XCTAssertNotNil(url)
        XCTAssertFalse(url!.path.hasPrefix("~"))
        XCTAssertTrue(url!.path.contains("Documents/Foo"))
    }

    func test_supportedFile_recognises_extensions() {
        XCTAssertTrue(SuperMDFile.isSupported(URL(fileURLWithPath: "/tmp/x.note")))
        XCTAssertTrue(SuperMDFile.isSupported(URL(fileURLWithPath: "/tmp/x.SPD")))
        XCTAssertTrue(SuperMDFile.isSupported(URL(fileURLWithPath: "/tmp/x.pdf")))
        XCTAssertTrue(SuperMDFile.isSupported(URL(fileURLWithPath: "/tmp/x.PNG")))
        XCTAssertFalse(SuperMDFile.isSupported(URL(fileURLWithPath: "/tmp/x.txt")))
        XCTAssertFalse(SuperMDFile.isSupported(URL(fileURLWithPath: "/tmp/x")))
    }
}
