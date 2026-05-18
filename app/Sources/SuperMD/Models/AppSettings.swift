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

    /// Translate the bits of settings the engine cares about into the
    /// SuperMDConfig kwargs the sidecar's convert.file RPC accepts in its
    /// `config` parameter. Keep keys aligned with src/supermd/config.py.
    func engineConfigDict() -> [String: Any] {
        var dict: [String: Any] = [
            "model": llm.defaultModelID,
            "prompt": templates.pageInstruction,
            "template": templates.resolvedBodyTemplate(),
            "output_path_template": templates.pathTemplate,
            "output_filename_template": templates.filenameTemplate,
            "defaults": [
                "cooldown": llm.cooldownSeconds,
            ],
        ]
        // The engine only invokes the title-generation pass when
        // note_title_prompt is a non-empty string. The default UI toggle
        // hands it a sensible default prompt; users can override later.
        if llm.generateTitles {
            dict["note_title_prompt"] =
                "Summarize this note in 3-6 words as a Markdown-safe title; reply with just the title."
        }
        return dict
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

enum BodyTemplateSource: String, Codable, CaseIterable, Identifiable {
    case inline = "Inline"
    case file = "From file"
    var id: Self { self }
}

struct TemplateSettings: Codable {
    var pathTemplate: String = "{{DATE:YYYY/MM MMM}}/{{file_basename}}"
    var filenameTemplate: String = "{{file_basename}}.md"

    /// Selects whether `bodyTemplate` (inline) or the file at
    /// `bodyTemplateFilePath` provides the engine's body template.
    var bodyTemplateSource: BodyTemplateSource = .inline
    var bodyTemplateFilePath: String? = nil

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

    /// Pick whichever body template the user has actually configured.
    /// In file mode we re-read on every call so an Obsidian-side edit of
    /// the template takes effect on the next conversion without restarting
    /// SuperMD. If reading fails for any reason, fall back to the inline
    /// body template so a missing file never produces an empty note.
    func resolvedBodyTemplate() -> String {
        guard bodyTemplateSource == .file,
              let path = bodyTemplateFilePath, !path.isEmpty else {
            return bodyTemplate
        }
        let expanded = (path as NSString).expandingTildeInPath
        if let data = try? String(contentsOfFile: expanded, encoding: .utf8) {
            return data
        }
        return bodyTemplate
    }
}

// MARK: - Advanced

struct AdvancedSettings: Codable {
    var sidecarLogLevel: String = "INFO"
    var runAtLogin: Bool = false
    var hideFromDock: Bool = false  // menu-bar only mode
    var notificationsOnSuccess: Bool = true
    var notificationsOnFailure: Bool = true
}
