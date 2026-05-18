import Foundation

/// Observable view-model for the conversion queue. Receives RPC events and
/// surfaces them as ordered rows the UI can render.
@MainActor
final class ConversionQueueModel: ObservableObject {
    @Published var rows: [JobRow] = []
    @Published var selection: Set<JobRow.ID> = []
    @Published var isPaused: Bool = false

    func enqueue(input: URL, output: URL?) {
        guard let output else {
            var row = JobRow(
                input: input,
                output: URL(fileURLWithPath: "/"),
                status: .failed,
                startedAt: Date()
            )
            row.error = "No output folder configured — open Settings → Output"
            rows.append(row)
            return
        }
        let row = JobRow(
            input: input,
            output: output,
            status: .queued,
            startedAt: Date()
        )
        rows.append(row)
        if !isPaused {
            dispatch(rowID: row.id)
        }
    }

    private func dispatch(rowID: JobRow.ID) {
        guard let i = rows.firstIndex(where: { $0.id == rowID }) else { return }
        let input = rows[i].input
        let output = rows[i].output
        Task {
            do {
                let taskID = try await AppModel.shared!.sidecar.client.convertFile(
                    input: input.path,
                    output: output.path
                )
                if let i = rows.firstIndex(where: { $0.id == rowID }) {
                    rows[i].sidecarTaskID = taskID
                }
            } catch {
                if let i = rows.firstIndex(where: { $0.id == rowID }) {
                    rows[i].status = .failed
                    rows[i].error = error.localizedDescription
                }
            }
        }
    }

    func recordUnsupported(input: URL) {
        var row = JobRow(
            input: input,
            output: URL(fileURLWithPath: "/"),
            status: .failed,
            startedAt: Date()
        )
        row.error = "Unsupported file type — only .note / .spd / .pdf / .png"
        rows.append(row)
    }

    func togglePause() {
        isPaused.toggle()
        if !isPaused {
            // Drain any rows that were queued while paused.
            let queued = rows.filter { $0.status == .queued && $0.sidecarTaskID == nil }
            for r in queued { dispatch(rowID: r.id) }
        }
    }

    func reprocessSelected() {
        for id in selection {
            guard let row = rows.first(where: { $0.id == id }) else { continue }
            Task {
                _ = try? await AppModel.shared!.sidecar.client.convertFile(
                    input: row.input.path,
                    output: row.output.path,
                    force: true
                )
            }
        }
    }

    // MARK: - Notification handlers (driven by AppModel)

    func handleStarted(_ p: [String: Any]) {
        guard let taskID = p["task_id"] as? String else { return }
        update(taskID: taskID) { $0.status = .running }
    }

    func handlePage(_ p: [String: Any]) {
        guard let taskID = p["task_id"] as? String,
              let page = p["page"] as? Int,
              let total = p["total"] as? Int else { return }
        update(taskID: taskID) {
            $0.currentPage = page
            $0.totalPages = total
        }
    }

    func handleFinished(_ p: [String: Any]) {
        guard let taskID = p["task_id"] as? String else { return }
        update(taskID: taskID) {
            $0.status = .done
            $0.finishedAt = Date()
            $0.durationMs = (p["duration_ms"] as? Int) ?? 0
        }
    }

    func handleSkipped(_ p: [String: Any]) {
        guard let taskID = p["task_id"] as? String else { return }
        update(taskID: taskID) {
            $0.status = .skipped
            $0.finishedAt = Date()
            $0.skipReason = (p["reason"] as? String) ?? "unknown"
        }
    }

    func handleFailed(_ p: [String: Any]) {
        guard let taskID = p["task_id"] as? String else { return }
        update(taskID: taskID) {
            $0.status = .failed
            $0.finishedAt = Date()
            $0.error = (p["error"] as? String) ?? "unknown"
        }
    }

    private func update(taskID: String, mutate: (inout JobRow) -> Void) {
        guard let i = rows.firstIndex(where: { $0.sidecarTaskID == taskID }) else { return }
        mutate(&rows[i])
    }
}

struct JobRow: Identifiable, Equatable {
    enum Status: String { case queued, running, done, skipped, failed }
    let id = UUID()
    var sidecarTaskID: String? = nil
    var input: URL
    var output: URL
    var status: Status = .queued
    var currentPage: Int = 0
    var totalPages: Int = 0
    var startedAt: Date = .now
    var finishedAt: Date? = nil
    var durationMs: Int = 0
    var error: String? = nil
    var skipReason: String? = nil
}
