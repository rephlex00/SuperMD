import Foundation

struct LLMModel: Identifiable, Hashable, Codable {
    var id: String
    var provider: String?
    var size: Int64?
}

struct ObsidianVault: Identifiable, Hashable, Codable {
    var id: String
    var name: String
    var path: String
    var exists: Bool
}

enum SuperMDFile {
    static let supportedExtensions: Set<String> = ["note", "spd", "pdf", "png"]
    static func isSupported(_ url: URL) -> Bool {
        supportedExtensions.contains(url.pathExtension.lowercased())
    }
}
