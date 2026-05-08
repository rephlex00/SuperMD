import Foundation
import CoreServices

/// Tiny FSEvents wrapper that watches a directory and reports newly-arrived
/// files (debounced).
final class InboxWatcher {
    static let shared = InboxWatcher()
    private init() {}

    private var stream: FSEventStreamRef?
    private var url: URL?
    private var callback: (([URL]) -> Void)?
    private var seen: Set<String> = []
    private var debounceTimer: Timer?

    func start(at url: URL, callback: @escaping ([URL]) -> Void) {
        stop()
        self.url = url
        self.callback = callback
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)

        // Seed with current contents so we don't fire for files that already exist.
        if let existing = try? FileManager.default.contentsOfDirectory(atPath: url.path) {
            seen = Set(existing)
        }

        var ctx = FSEventStreamContext(version: 0, info: Unmanaged.passUnretained(self).toOpaque(),
                                       retain: nil, release: nil, copyDescription: nil)
        let pathsToWatch = [url.path] as CFArray
        let stream = FSEventStreamCreate(
            kCFAllocatorDefault,
            { _, info, _, _, _, _ in
                guard let info else { return }
                let me = Unmanaged<InboxWatcher>.fromOpaque(info).takeUnretainedValue()
                me.scheduleScan()
            },
            &ctx,
            pathsToWatch,
            FSEventStreamEventId(kFSEventStreamEventIdSinceNow),
            1.0,
            UInt32(kFSEventStreamCreateFlagFileEvents)
        )
        if let stream {
            FSEventStreamSetDispatchQueue(stream, .main)
            FSEventStreamStart(stream)
            self.stream = stream
        }
    }

    func stop() {
        if let stream {
            FSEventStreamStop(stream)
            FSEventStreamInvalidate(stream)
            FSEventStreamRelease(stream)
        }
        stream = nil
        seen = []
        debounceTimer?.invalidate()
        debounceTimer = nil
    }

    private func scheduleScan() {
        debounceTimer?.invalidate()
        debounceTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: false) { [weak self] _ in
            self?.scanAndReport()
        }
    }

    private func scanAndReport() {
        guard let url, let callback else { return }
        let current = (try? FileManager.default.contentsOfDirectory(atPath: url.path)) ?? []
        let newFiles = current.filter { !seen.contains($0) }
        seen = Set(current)
        let urls = newFiles
            .map { url.appendingPathComponent($0) }
            .filter { SuperMDFile.isSupported($0) }
        if !urls.isEmpty {
            callback(urls)
        }
    }
}
