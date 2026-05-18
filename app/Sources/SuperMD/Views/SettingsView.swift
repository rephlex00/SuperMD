import SwiftUI

struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettingsTab()
                .tabItem { Label("General", systemImage: "gearshape") }
            LLMSettingsTab()
                .tabItem { Label("LLM", systemImage: "brain") }
            CloudSettingsTab()
                .tabItem { Label("Cloud", systemImage: "icloud") }
            OutputSettingsTab()
                .tabItem { Label("Output", systemImage: "doc.text") }
            TemplateSettingsTab()
                .tabItem { Label("Templates", systemImage: "curlybraces.square") }
            AdvancedSettingsTab()
                .tabItem { Label("Advanced", systemImage: "wrench.and.screwdriver") }
        }
        .padding(20)
    }
}

// MARK: - General

struct GeneralSettingsTab: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        Form {
            Section {
                Toggle("Accept files dropped on the window or dock icon",
                       isOn: $app.settings.input.dragAndDropEnabled)
            } header: { Text("Drag-and-drop") } footer: {
                Text("When off, dragged files are ignored. AppleEvent opens are also blocked.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            Section {
                Toggle("Watch this folder and auto-convert new files",
                       isOn: $app.settings.input.watchInbox)
                HStack {
                    TextField("Inbox path", text: $app.settings.input.inboxPath)
                        .disabled(!app.settings.input.watchInbox)
                    Button("Choose…") { pickInbox() }
                        .disabled(!app.settings.input.watchInbox)
                    Button("Reveal") {
                        if let url = app.settings.input.inboxURL {
                            NSWorkspace.shared.activateFileViewerSelecting([url])
                        }
                    }
                    .disabled(!app.settings.input.watchInbox)
                }
            } header: { Text("Inbox folder") } footer: {
                Text("New .note / .spd / .pdf / .png files saved here are picked up and converted automatically.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            Section {
                Toggle("Open SuperMD at login", isOn: $app.settings.advanced.runAtLogin)
                Toggle("Hide from Dock (menu-bar only)", isOn: $app.settings.advanced.hideFromDock)
            } header: { Text("Startup") } footer: {
                Text("Menu-bar-only mode skips the Dock icon. You can still reach the main window through the menu-bar extra.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            Section {
                Toggle("Notify when a conversion finishes",
                       isOn: $app.settings.advanced.notificationsOnSuccess)
                Toggle("Notify when a conversion fails",
                       isOn: $app.settings.advanced.notificationsOnFailure)
            } header: { Text("Notifications") } footer: {
                Text("macOS will ask for notification permission the first time SuperMD wants to send one.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }

    private func pickInbox() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            app.settings.input.inboxPath = url.path
        }
    }
}

// MARK: - LLM

struct LLMSettingsTab: View {
    @EnvironmentObject var app: AppModel
    @State private var apiKey: String = ""
    @State private var keyTestStatus: KeyTestStatus = .idle

    enum KeyTestStatus { case idle, testing, ok, failed(String) }

    var body: some View {
        Form {
            Section("Provider & model") {
                Picker("Provider", selection: $app.settings.llm.provider) {
                    ForEach(LLMProvider.allCases) { p in Text(p.rawValue).tag(p) }
                }
                modelPicker
            }
            if app.settings.llm.provider != .ollama {
                Section {
                    if keySavedForCurrentProvider {
                        Label("A \(app.settings.llm.provider.rawValue) key is saved in Keychain.",
                              systemImage: "checkmark.seal.fill")
                            .foregroundStyle(.green)
                    }
                    SecureField("Paste your \(app.settings.llm.provider.rawValue) API key",
                                text: $apiKey)
                    HStack {
                        Button(testing ? "Testing…" : (keySavedForCurrentProvider ? "Replace key" : "Test & save")) { testAndSave() }
                            .disabled(apiKey.isEmpty || testing)
                        Spacer()
                        statusBadge
                    }
                } header: { Text("API key") } footer: {
                    Text("Stored in macOS Keychain (service com.supermd.app). \"Test & save\" sends a 1-token probe to confirm the key works before persisting.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            } else {
                Section {
                    OllamaStatusView()
                } header: { Text("Ollama") } footer: {
                    Text("SuperMD talks to Ollama at http://127.0.0.1:11434 — install and run Ollama separately.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Section {
                Toggle("Generate a short title for each note",
                       isOn: $app.settings.llm.generateTitles)
                Stepper(value: $app.settings.llm.cooldownSeconds, in: 0...60, step: 1) {
                    Text("Cooldown between page calls: \(Int(app.settings.llm.cooldownSeconds))s")
                }
            } header: { Text("Behavior") } footer: {
                Text("Title generation makes a second LLM call per note. Cooldown helps avoid rate limits on free-tier API keys.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }

    private var keySavedForCurrentProvider: Bool {
        let key: String = {
            switch app.settings.llm.provider {
            case .openai: return "openai"
            case .anthropic: return "anthropic"
            case .gemini: return "gemini"
            case .ollama: return "ollama"
            }
        }()
        return app.settings.llm.apiKeyPresent[key] == true
    }

    private var testing: Bool {
        if case .testing = keyTestStatus { return true }
        return false
    }

    @ViewBuilder
    private var modelPicker: some View {
        switch app.llmAvailability {
        case .available(let api, let ollama):
            let pool = app.settings.llm.provider == .ollama ? ollama : api
            Picker("Model", selection: $app.settings.llm.defaultModelID) {
                ForEach(pool) { m in Text(m.id).tag(m.id) }
            }
        default:
            TextField("Model ID", text: $app.settings.llm.defaultModelID)
        }
    }

    @ViewBuilder
    private var statusBadge: some View {
        switch keyTestStatus {
        case .idle: EmptyView()
        case .testing: ProgressView().controlSize(.small)
        case .ok: Label("Saved", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
        case .failed(let s): Label(s, systemImage: "xmark.circle.fill").foregroundStyle(.red)
        }
    }

    private func testAndSave() {
        let providerKey: String = {
            switch app.settings.llm.provider {
            case .openai: return "openai"
            case .anthropic: return "anthropic"
            case .gemini: return "gemini"
            case .ollama: return "ollama"
            }
        }()
        keyTestStatus = .testing
        Task {
            do {
                try await app.sidecar.client.testLLMKey(provider: providerKey, key: apiKey)
                try await app.sidecar.client.setLLMKey(provider: providerKey, key: apiKey)
                app.settings.llm.apiKeyPresent[providerKey] = true
                keyTestStatus = .ok
                apiKey = ""  // clear from memory once saved to keychain
            } catch {
                keyTestStatus = .failed(error.localizedDescription)
            }
        }
    }
}

private struct OllamaStatusView: View {
    @EnvironmentObject var app: AppModel
    @State private var running: Bool? = nil
    @State private var refreshing = false

    var body: some View {
        HStack {
            if let running {
                Label(running ? "Ollama is running" : "Ollama not detected on localhost:11434",
                      systemImage: running ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundStyle(running ? .green : .red)
            } else {
                ProgressView().controlSize(.small)
            }
            Spacer()
            Button(refreshing ? "Refreshing…" : "Refresh") { refresh() }
                .disabled(refreshing)
        }
        .onAppear { refresh() }
    }

    private func refresh() {
        refreshing = true
        Task {
            running = (try? await app.sidecar.client.ollamaStatus()) ?? false
            refreshing = false
        }
    }
}

// MARK: - Cloud

struct CloudSettingsTab: View {
    @EnvironmentObject var app: AppModel
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var working = false
    @State private var error: String?

    var body: some View {
        Form {
            switch app.cloudStatus {
            case .signedIn(let signedEmail):
                Section {
                    Label("Signed in as \(signedEmail)", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(.green)
                    Toggle("Auto-sync new notes into the Inbox",
                           isOn: $app.settings.input.cloudSyncEnabled)
                        .onChange(of: app.settings.input.cloudSyncEnabled) { _, on in
                            Task { on ? await app.startCloudSync() : await app.stopCloudSync() }
                        }
                    TextField("Remote folder", text: $app.settings.input.cloudRemotePath)
                        .disabled(!app.settings.input.cloudSyncEnabled)
                    Stepper(value: $app.settings.input.cloudIntervalSec, in: 60...3600, step: 60) {
                        Text("Check every \(intervalLabel(app.settings.input.cloudIntervalSec))")
                    }
                    .disabled(!app.settings.input.cloudSyncEnabled)
                    Button("Sign out", role: .destructive) { signOut() }
                } footer: {
                    Text("New notes from your Supernote Cloud account get downloaded into the Inbox folder and are converted automatically.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            default:
                Section("Sign in to Supernote Cloud") {
                    TextField("Email", text: $email)
                        .textContentType(.emailAddress)
                    SecureField("Password", text: $password)
                    if let error {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }
                    HStack {
                        Spacer()
                        Button(working ? "Signing in…" : "Sign in") { signIn() }
                            .disabled(email.isEmpty || password.isEmpty || working)
                            .keyboardShortcut(.return)
                    }
                }
            }
        }
        .formStyle(.grouped)
    }

    private func signIn() {
        working = true
        error = nil
        Task {
            do {
                let token = try await app.sidecar.client.cloudLogin(email: email, password: password)
                app.settings.input.cloudEmail = email
                app.settings.input.cloudToken = token
                app.cloudStatus = .signedIn(email: email)
                password = ""
            } catch {
                self.error = error.localizedDescription
            }
            working = false
        }
    }

    private func intervalLabel(_ secs: Int) -> String {
        if secs < 60 { return "\(secs) seconds" }
        let m = secs / 60
        return m == 1 ? "1 minute" : "\(m) minutes"
    }

    private func signOut() {
        Task {
            try? await app.sidecar.client.cloudLogout()
            app.settings.input.cloudEmail = nil
            app.settings.input.cloudToken = nil
            app.settings.input.cloudSyncEnabled = false
            app.cloudStatus = .signedOut
        }
    }
}

// MARK: - Output

struct OutputSettingsTab: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        Form {
            Section {
                Picker("Mode", selection: $app.settings.output.mode) {
                    ForEach(ObsidianMode.allCases) { Text($0.rawValue).tag($0) }
                }
            } header: { Text("Where converted notes land") } footer: {
                modeFooter
            }

            switch app.settings.output.mode {
            case .vault, .headless:
                vaultSection
                Section("After conversion") {
                    Toggle("Open new notes in Obsidian",
                           isOn: $app.settings.output.openInObsidianAfter)
                        .disabled(app.settings.output.selectedVaultID == nil)
                }
            case .folder:
                folderSection
            }
        }
        .formStyle(.grouped)
    }

    @ViewBuilder
    private var modeFooter: some View {
        switch app.settings.output.mode {
        case .vault:
            Text("Drops notes into a real Obsidian vault on disk. SuperMD will offer to open each new note in Obsidian after conversion.")
                .font(.caption).foregroundStyle(.secondary)
        case .folder:
            Text("Saves Markdown to any folder. Useful when you don't use Obsidian.")
                .font(.caption).foregroundStyle(.secondary)
        case .headless:
            Text("Runs an obsidian-headless background process against the vault — for power users who want plugin processing without an open Obsidian window.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private var vaultSection: some View {
        Section {
            if app.settings.output.discoveredVaults.isEmpty {
                Label("No Obsidian vaults found.", systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.orange)
                Text("Open Obsidian at least once so it registers a vault, or switch to \"Generic output folder\" mode.")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                Picker("Vault", selection: $app.settings.output.selectedVaultID) {
                    Text("Select a vault…").tag(String?.none)
                    ForEach(app.settings.output.discoveredVaults) { v in
                        Text(v.name).tag(Optional(v.id))
                    }
                }
                .onChange(of: app.settings.output.selectedVaultID) { _, newID in
                    if let v = app.settings.output.discoveredVaults.first(where: { $0.id == newID }) {
                        app.settings.output.selectedVaultPath = v.path
                    }
                }
                if let v = app.settings.output.discoveredVaults.first(where: { $0.id == app.settings.output.selectedVaultID }) {
                    Text(v.path)
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                }
            }
            TextField("Subfolder inside the vault", text: $app.settings.output.subfolderInVault)
                .disabled(app.settings.output.selectedVaultID == nil)
        } header: { Text("Vault") } footer: {
            Text("Notes are written under <vault>/<subfolder>/…")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private var folderSection: some View {
        Section("Output folder") {
            HStack {
                TextField("Path", text: $app.settings.output.genericOutputPath)
                Button("Choose…") {
                    let panel = NSOpenPanel()
                    panel.canChooseFiles = false
                    panel.canChooseDirectories = true
                    if panel.runModal() == .OK, let url = panel.url {
                        app.settings.output.genericOutputPath = url.path
                    }
                }
            }
        }
    }
}

private struct FolderMappingEditor: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach($app.settings.output.perFolderMappings) { $m in
                HStack {
                    TextField("Source prefix", text: $m.sourcePrefix)
                    Image(systemName: "arrow.right")
                    TextField("Destination template", text: $m.destination)
                    Button(role: .destructive) {
                        app.settings.output.perFolderMappings.removeAll { $0.id == m.id }
                    } label: { Image(systemName: "minus.circle") }
                    .buttonStyle(.borderless)
                }
            }
            Button {
                app.settings.output.perFolderMappings.append(
                    FolderMapping(sourcePrefix: "", destination: "")
                )
            } label: {
                Label("Add mapping", systemImage: "plus")
            }
            .buttonStyle(.borderless)
        }
    }
}

// MARK: - Templates

struct TemplateSettingsTab: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        Form {
            Section {
                TextField("Folder template", text: $app.settings.templates.pathTemplate)
                TextField("Filename template", text: $app.settings.templates.filenameTemplate)
            } header: { Text("Output paths") } footer: {
                Text("Tokens: {{file_basename}}, {{title}}, {{DATE:YYYY/MM-DD}}, {{year}}, {{month}}, {{day}}. Title only resolves if \"Generate a short title\" is on.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            BodyTemplateSection()

            Section {
                TextEditor(text: $app.settings.templates.pageInstruction)
                    .font(.system(.body, design: .monospaced))
                    .frame(minHeight: 100)
                Button("Reset to default") {
                    app.settings.templates.pageInstruction = TemplateSettings().pageInstruction
                }
            } header: { Text("Per-page LLM instruction") } footer: {
                Text("Sent to the model with every page image. Lean on this to control style (Markdown flavor, math syntax, wiki-links, etc.).")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }
}

/// Body-template section with two modes: inline (stored in UserDefaults) or
/// an external Markdown file (typically inside an Obsidian vault's Templates
/// folder). In file mode we read on appear, give the user Save/Reload, and
/// the engine re-reads on every convert so Obsidian-side edits take effect.
private struct BodyTemplateSection: View {
    @EnvironmentObject var app: AppModel
    @State private var fileContents: String = ""
    @State private var fileStatus: FileStatus = .idle

    enum FileStatus: Equatable {
        case idle
        case loaded
        case saved
        case error(String)
    }

    var body: some View {
        Section {
            Picker("Source", selection: $app.settings.templates.bodyTemplateSource) {
                ForEach(BodyTemplateSource.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .onChange(of: app.settings.templates.bodyTemplateSource) { _, new in
                if new == .file { loadFromFile() }
            }

            switch app.settings.templates.bodyTemplateSource {
            case .inline:
                TextEditor(text: $app.settings.templates.bodyTemplate)
                    .font(.system(.body, design: .monospaced))
                    .frame(minHeight: 140)
                Button("Reset to default") {
                    app.settings.templates.bodyTemplate = TemplateSettings().bodyTemplate
                }
            case .file:
                HStack {
                    TextField("Path to Markdown template",
                              text: Binding(
                                get: { app.settings.templates.bodyTemplateFilePath ?? "" },
                                set: { app.settings.templates.bodyTemplateFilePath = $0.isEmpty ? nil : $0 }))
                    Button("Choose…") { chooseFile() }
                    Button("Reveal") { revealFile() }
                        .disabled(app.settings.templates.bodyTemplateFilePath == nil)
                }
                TextEditor(text: $fileContents)
                    .font(.system(.body, design: .monospaced))
                    .frame(minHeight: 140)
                    .disabled(app.settings.templates.bodyTemplateFilePath == nil)
                HStack {
                    Button("Reload from file") { loadFromFile() }
                        .disabled(app.settings.templates.bodyTemplateFilePath == nil)
                    Spacer()
                    statusBadge
                    Button("Save to file") { saveToFile() }
                        .keyboardShortcut("s")
                        .disabled(app.settings.templates.bodyTemplateFilePath == nil)
                }
            }
        } header: { Text("Body template") } footer: {
            VStack(alignment: .leading, spacing: 4) {
                Text("Jinja2 template wrapped around the model's transcription. Must contain {{llm_output}} somewhere or your notes will be empty.")
                if app.settings.templates.bodyTemplateSource == .file {
                    Text("Tip: point this at a file inside your Obsidian vault's Templates folder so you can edit it in Obsidian too. The file is re-read on every conversion.")
                }
            }
            .font(.caption).foregroundStyle(.secondary)
        }
        .onAppear {
            if app.settings.templates.bodyTemplateSource == .file { loadFromFile() }
        }
    }

    @ViewBuilder
    private var statusBadge: some View {
        switch fileStatus {
        case .idle: EmptyView()
        case .loaded:
            Label("Loaded", systemImage: "doc.text.fill")
                .foregroundStyle(.secondary).font(.caption)
        case .saved:
            Label("Saved", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green).font(.caption)
        case .error(let s):
            Label(s, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.red).font(.caption).lineLimit(1)
        }
    }

    private var resolvedPath: String? {
        guard let p = app.settings.templates.bodyTemplateFilePath, !p.isEmpty else { return nil }
        return (p as NSString).expandingTildeInPath
    }

    private func chooseFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.text, .plainText]
        panel.allowsOtherFileTypes = true  // .md not always registered
        if let vault = app.settings.output.selectedVaultPath {
            panel.directoryURL = URL(fileURLWithPath: (vault as NSString).expandingTildeInPath)
        }
        if panel.runModal() == .OK, let url = panel.url {
            app.settings.templates.bodyTemplateFilePath = url.path
            loadFromFile()
        }
    }

    private func revealFile() {
        guard let path = resolvedPath else { return }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }

    private func loadFromFile() {
        guard let path = resolvedPath else {
            fileStatus = .error("No file selected")
            return
        }
        do {
            fileContents = try String(contentsOfFile: path, encoding: .utf8)
            fileStatus = .loaded
        } catch {
            fileContents = ""
            fileStatus = .error("Couldn't read: \(error.localizedDescription)")
        }
    }

    private func saveToFile() {
        guard let path = resolvedPath else { return }
        do {
            try fileContents.write(toFile: path, atomically: true, encoding: .utf8)
            fileStatus = .saved
        } catch {
            fileStatus = .error("Couldn't write: \(error.localizedDescription)")
        }
    }
}

// MARK: - Advanced

struct AdvancedSettingsTab: View {
    @EnvironmentObject var app: AppModel
    @State private var configYaml: String = ""

    var body: some View {
        Form {
            Section {
                Picker("Sidecar log level", selection: $app.settings.advanced.sidecarLogLevel) {
                    ForEach(["DEBUG", "INFO", "WARNING", "ERROR"], id: \.self) {
                        Text($0).tag($0)
                    }
                }
                .onChange(of: app.settings.advanced.sidecarLogLevel) { _, level in
                    Task { try? await app.sidecar.client.setLogLevel(level) }
                }
                Button("Open log directory") {
                    Task {
                        if let p = try? await app.sidecar.client.configPath().logDir {
                            NSWorkspace.shared.open(URL(fileURLWithPath: p))
                        }
                    }
                }
            } header: { Text("Logging") } footer: {
                Text("Changes apply to the running sidecar immediately. DEBUG is noisy — leave on INFO unless investigating an issue.")
                    .font(.caption).foregroundStyle(.secondary)
            }

            Section {
                TextEditor(text: $configYaml)
                    .font(.system(.body, design: .monospaced))
                    .frame(minHeight: 240)
                HStack {
                    Button("Reload from disk") { reload() }
                    Spacer()
                    Button("Save") { save() }.keyboardShortcut("s")
                }
            } header: { Text("On-disk YAML config") } footer: {
                Text("Direct edit of <config_dir>/supermd.yaml — only the CLI and headless runs read this file. The macOS app reads its own UI settings; use this tab to keep them in sync if you also run the CLI.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .onAppear { reload() }
    }

    private func reload() {
        Task {
            if let r = try? await app.sidecar.client.readConfig() {
                configYaml = r.yaml
            }
        }
    }

    private func save() {
        Task { try? await app.sidecar.client.writeConfig(yaml: configYaml) }
    }
}
