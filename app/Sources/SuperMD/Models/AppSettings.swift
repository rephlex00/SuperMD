import Foundation
import SwiftUI

/// User-visible settings, persisted to UserDefaults as a single JSON blob.
/// The on-disk YAML config (used by the engine when run from the CLI) is a
/// separate concern; the host derives that YAML from this struct on save.
final class AppSettings: ObservableObject {
    @Published var input = InputSettings()
    @Published var output = OutputSettings()
    @Published var llm = LLMSettings()
    @Published var templates = TemplateSettings()
    @Published var advanced = AdvancedSettings()

    private static let storeKey = "com.supermd.app.settings.v1"

    static func load() -> AppSettings {
        let s = AppSettings()
        guard let data = UserDefaults.standard.data(forKey: storeKey) else { return s }
        if let raw = try? JSONDecoder().decode(SettingsBlob.self, from: data) {
            s.input = raw.input
            s.output = raw.output
            s.llm = raw.llm
            s.templates = raw.templates
            s.advanced = raw.advanced
        }
        return s
    }

    func save() {
        let blob = SettingsBlob(
            input: input,
            output: output,
            llm: llm,
            templates: templates,
            advanced: advanced
        )
        if let data = try? JSONEncoder().encode(blob) {
            UserDefaults.standard.set(data, forKey: Self.storeKey)
        }
    }
}

private struct SettingsBlob: Codable {
    var input: InputSettings
    var output: OutputSettings
    var llm: LLMSettings
    var templates: TemplateSettings
    var advanced: AdvancedSettings
}

// MARK: - Input

struct InputSettings: Codable {
    var dragAndDropEnabled: Bool = true

    var watchInbox: Bool = true
    var inboxPath: String = "~/Documents/Supernote Inbox"
    var inboxURL: URL? {
        URL(fileURLWithPath: (inboxPath as NSString).expandingTildeInPath)
    }

    var cloudSyncEnabled: Bool = false
    var cloudEmail: String? = nil
    var cloudToken: String? = nil          // JWT in Keychain ideally, here for v0
    var cloudRemotePath: String = "/Note"
    var cloudIntervalSec: Int = 300
}

// MARK: - Output

enum ObsidianMode: String, Codable, CaseIterable, Identifiable {
    case vault = "Pick a vault"
    case folder = "Generic output folder"
    case headless = "Headless Obsidian (advanced)"
    var id: Self { self }
}

struct OutputSettings: Codable {
    var mode: ObsidianMode = .vault
    var selectedVaultID: String? = nil
    var selectedVaultPath: String? = nil
    var subfolderInVault: String = "Supernote"
    var openInObsidianAfter: Bool = true

    var genericOutputPath: String = "~/Documents/Supernote Markdown"

    /// Folder mappings: source-prefix -> destination-relative-to-output.
    var perFolderMappings: [FolderMapping] = []

    var resolvedRoot: URL? {
        switch mode {
        case .vault, .headless:
            guard let p = selectedVaultPath else { return nil }
            return URL(fileURLWithPath: (p as NSString).expandingTildeInPath)
                .appendingPathComponent(subfolderInVault, isDirectory: true)
        case .folder:
            return URL(fileURLWithPath: (genericOutputPath as NSString).expandingTildeInPath)
        }
    }

    // Discovered at runtime, not persisted (reset on each launch).
    var discoveredVaults: [ObsidianVault] = []

    enum CodingKeys: String, CodingKey {
        case mode, selectedVaultID, selectedVaultPath, subfolderInVault,
             openInObsidianAfter, genericOutputPath, perFolderMappings
    }
}

struct FolderMapping: Codable, Identifiable, Hashable {
    var id = UUID()
    var sourcePrefix: String  // e.g. "Inbox/Journal/" or "Cloud:/Note/"
    var destination: String   // Jinja2 template, e.g. "Daily/{{DATE:YYYY-MM}}/"
}

// MARK: - LLM

enum LLMProvider: String, Codable, CaseIterable, Identifiable {
    case openai = "OpenAI"
    case anthropic = "Anthropic"
    case gemini = "Gemini"
    case ollama = "Ollama (local)"
    var id: Self { self }
}

struct LLMSettings: Codable {
    var provider: LLMProvider = .openai
    var defaultModelID: String = "gpt-4o-mini"
    var titleModelID: String? = nil
    var generateTitles: Bool = false
    var cooldownSeconds: Double = 5.0
    /// Whether each provider has an API key stored in the Keychain.
    var apiKeyPresent: [String: Bool] = [:]
}

// MARK: - Templates

struct TemplateSettings: Codable {
    var pathTemplate: String = "{{DATE:YYYY/MM MMM}}/{{file_basename}}"
    var filenameTemplate: String = "{{file_basename}}.md"
    var bodyTemplate: String = """
    ---
    created: {{DATE:YYYY-MM-DD}}
    tags: supernote
    source: supernote
    ---

    {{llm_output}}
    """
    var pageInstruction: String = """
    Convert the image to markdown. Use mermaid for simple diagrams, $$ for math,
    and Obsidian wiki-link syntax where appropriate. Do not wrap text in code blocks.
    """
}

// MARK: - Advanced

struct AdvancedSettings: Codable {
    var sidecarLogLevel: String = "INFO"
    var runAtLogin: Bool = false
    var hideFromDock: Bool = false  // menu-bar only mode
    var notificationsOnSuccess: Bool = true
    var notificationsOnFailure: Bool = true
}
