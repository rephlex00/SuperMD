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

    private func dispatch(rowID: JobRow.ID, force: Bool = false) {
        guard let i = rows.firstIndex(where: { $0.id == rowID }) else { return }
        let input = rows[i].input
        let output = rows[i].output
        let settings = AppModel.shared!.settings
        let model = settings.llm.defaultModelID
        let config = settings.engineConfigDict()
        Task {
            do {
                let taskID = try await AppModel.shared!.sidecar.client.convertFile(
                    input: input.path,
                    output: output.path,
                    model: model,
                    force: force,
                    config: config
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

    func cancelSelected() {
        for id in selection {
            cancel(rowID: id)
        }
    }

    func cancel(rowID: JobRow.ID) {
        guard let i = rows.firstIndex(where: { $0.id == rowID }) else { return }
        let taskID = rows[i].sidecarTaskID
        // Queued (not yet dispatched) rows are pure-local cancellations.
        if rows[i].status == .queued, taskID == nil {
            rows.remove(at: i)
            return
        }
        // In-flight: ask the sidecar to stop, then mark failed.
        if let taskID {
            Task { try? await AppModel.shared!.sidecar.client.convertCancel(taskID: taskID) }
        }
        rows[i].status = .failed
        rows[i].error = "Cancelled"
        rows[i].finishedAt = Date()
    }

    func reprocessSelected() {
        for id in selection {
            dispatch(rowID: id, force: true)
        }
    }

    /// Re-run a single row with force=true. Used by the per-row "Run again"
    /// button and the row context menu — most useful for rows that finished
    /// .skipped but the user actually wants converted again.
    func forceRerun(rowID: JobRow.ID) {
        guard let i = rows.firstIndex(where: { $0.id == rowID }) else { return }
        rows[i].status = .queued
        rows[i].sidecarTaskID = nil
        rows[i].error = nil
        rows[i].skipReason = nil
        rows[i].finishedAt = nil
        rows[i].currentPage = 0
        rows[i].totalPages = 0
        rows[i].durationMs = 0
        if !isPaused {
            dispatch(rowID: rowID, force: true)
        }
    }

    /// Remove a row entirely (after cancelling the in-flight task if any).
    func remove(rowID: JobRow.ID) {
        guard let i = rows.firstIndex(where: { $0.id == rowID }) else { return }
        if let taskID = rows[i].sidecarTaskID, rows[i].status == .running || rows[i].status == .queued {
            Task { try? await AppModel.shared!.sidecar.client.convertCancel(taskID: taskID) }
        }
        rows.remove(at: i)
        selection.remove(rowID)
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
