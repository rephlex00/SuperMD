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
            ObsidianSettingsTab()
                .tabItem { Label("Obsidian", systemImage: "doc.text") }
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
            Section("Drag-and-drop") {
                Toggle("Accept files dropped on the app or dock icon",
                       isOn: $app.settings.input.dragAndDropEnabled)
            }
            Section("Watched Inbox folder") {
                Toggle("Auto-convert files placed in this folder",
                       isOn: $app.settings.input.watchInbox)
                HStack {
                    TextField("Inbox path", text: $app.settings.input.inboxPath)
                    Button("Choose…") { pickInbox() }
                    Button("Reveal") {
                        if let url = app.settings.input.inboxURL {
                            NSWorkspace.shared.activateFileViewerSelecting([url])
                        }
                    }
                }
            }
            Section("System") {
                Toggle("Run at login", isOn: $app.settings.advanced.runAtLogin)
                Toggle("Hide from Dock (menu-bar only)", isOn: $app.settings.advanced.hideFromDock)
                Toggle("Notify on success", isOn: $app.settings.advanced.notificationsOnSuccess)
                Toggle("Notify on failure", isOn: $app.settings.advanced.notificationsOnFailure)
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
            Section("Default model") {
                Picker("Provider", selection: $app.settings.llm.provider) {
                    ForEach(LLMProvider.allCases) { p in Text(p.rawValue).tag(p) }
                }
                modelPicker
            }
            if app.settings.llm.provider != .ollama {
                Section("API key") {
                    SecureField("Paste your \(app.settings.llm.provider.rawValue) API key",
                                text: $apiKey)
                    HStack {
                        Button(testing ? "Testing…" : "Test & save") { testAndSave() }
                            .disabled(apiKey.isEmpty || testing)
                        Spacer()
                        statusBadge
                    }
                }
            } else {
                Section("Ollama") {
                    OllamaStatusView()
                }
            }
            Section("Behavior") {
                Toggle("Generate a short title for each note", isOn: $app.settings.llm.generateTitles)
                Stepper(value: $app.settings.llm.cooldownSeconds, in: 0...60, step: 1) {
                    Text("Cooldown between page calls: \(Int(app.settings.llm.cooldownSeconds))s")
                }
            }
        }
        .formStyle(.grouped)
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
                    Toggle("Auto-sync", isOn: $app.settings.input.cloudSyncEnabled)
                    TextField("Remote path", text: $app.settings.input.cloudRemotePath)
                    Stepper(value: $app.settings.input.cloudIntervalSec, in: 60...3600, step: 60) {
                        Text("Sync every \(app.settings.input.cloudIntervalSec)s")
                    }
                    Button("Sign out", role: .destructive) { signOut() }
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

// MARK: - Obsidian

struct ObsidianSettingsTab: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        Form {
            Section("Mode") {
                Picker("Output mode", selection: $app.settings.output.mode) {
                    ForEach(ObsidianMode.allCases) { Text($0.rawValue).tag($0) }
                }
            }
            switch app.settings.output.mode {
            case .vault, .headless:
                vaultSection
            case .folder:
                folderSection
            }
            Section("After conversion") {
                Toggle("Open new notes in Obsidian", isOn: $app.settings.output.openInObsidianAfter)
            }
            Section("Per-folder mappings") {
                FolderMappingEditor()
            }
        }
        .formStyle(.grouped)
    }

    @ViewBuilder
    private var vaultSection: some View {
        Section("Vault") {
            Picker("Vault", selection: $app.settings.output.selectedVaultID) {
                Text("None").tag(String?.none)
                ForEach(app.settings.output.discoveredVaults) { v in
                    Text("\(v.name)  \(v.path)").tag(Optional(v.id))
                }
            }
            .onChange(of: app.settings.output.selectedVaultID) { _, newID in
                if let v = app.settings.output.discoveredVaults.first(where: { $0.id == newID }) {
                    app.settings.output.selectedVaultPath = v.path
                }
            }
            TextField("Subfolder in vault", text: $app.settings.output.subfolderInVault)
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
            Section("Output paths") {
                TextField("Folder template", text: $app.settings.templates.pathTemplate)
                TextField("Filename template", text: $app.settings.templates.filenameTemplate)
                Text("Tokens: {{file_basename}}, {{title}}, {{DATE:YYYY/MM-DD}}, {{year}}, {{month}}.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Body template") {
                TextEditor(text: $app.settings.templates.bodyTemplate)
                    .font(.system(.body, design: .monospaced))
                    .frame(minHeight: 140)
            }
            Section("Per-page LLM instruction") {
                TextEditor(text: $app.settings.templates.pageInstruction)
                    .font(.system(.body, design: .monospaced))
                    .frame(minHeight: 100)
            }
        }
        .formStyle(.grouped)
    }
}

// MARK: - Advanced

struct AdvancedSettingsTab: View {
    @EnvironmentObject var app: AppModel
    @State private var configYaml: String = ""

    var body: some View {
        Form {
            Section("Logging") {
                Picker("Sidecar log level", selection: $app.settings.advanced.sidecarLogLevel) {
                    ForEach(["DEBUG", "INFO", "WARNING", "ERROR"], id: \.self) {
                        Text($0).tag($0)
                    }
                }
                Button("Open log directory") {
                    Task {
                        if let p = try? await app.sidecar.client.configPath().logDir {
                            NSWorkspace.shared.open(URL(fileURLWithPath: p))
                        }
                    }
                }
            }
            Section("On-disk YAML config") {
                TextEditor(text: $configYaml)
                    .font(.system(.body, design: .monospaced))
                    .frame(minHeight: 240)
                HStack {
                    Button("Reload from disk") { reload() }
                    Spacer()
                    Button("Save") { save() }.keyboardShortcut("s")
                }
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
