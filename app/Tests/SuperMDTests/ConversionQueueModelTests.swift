import XCTest
@testable import SuperMD

@MainActor
final class ConversionQueueModelTests: XCTestCase {
    func test_handleStarted_marks_row_running() {
        let queue = ConversionQueueModel()
        var row = JobRow(input: URL(fileURLWithPath: "/tmp/a.note"),
                         output: URL(fileURLWithPath: "/tmp"))
        row.sidecarTaskID = "conv-1"
        queue.rows.append(row)

        queue.handleStarted(["task_id": "conv-1"])
        XCTAssertEqual(queue.rows.first?.status, .running)
    }

    func test_handlePage_updates_progress_counters() {
        let queue = ConversionQueueModel()
        var row = JobRow(input: URL(fileURLWithPath: "/tmp/a.note"),
                         output: URL(fileURLWithPath: "/tmp"))
        row.sidecarTaskID = "conv-1"
        queue.rows.append(row)

        queue.handlePage(["task_id": "conv-1", "page": 3, "total": 7])
        XCTAssertEqual(queue.rows.first?.currentPage, 3)
        XCTAssertEqual(queue.rows.first?.totalPages, 7)
    }

    func test_handleFinished_records_duration() {
        let queue = ConversionQueueModel()
        var row = JobRow(input: URL(fileURLWithPath: "/tmp/a.note"),
                         output: URL(fileURLWithPath: "/tmp"))
        row.sidecarTaskID = "conv-1"
        queue.rows.append(row)

        queue.handleFinished(["task_id": "conv-1", "duration_ms": 4242])
        XCTAssertEqual(queue.rows.first?.status, .done)
        XCTAssertEqual(queue.rows.first?.durationMs, 4242)
    }

    func test_handleFailed_captures_error_message() {
        let queue = ConversionQueueModel()
        var row = JobRow(input: URL(fileURLWithPath: "/tmp/a.note"),
                         output: URL(fileURLWithPath: "/tmp"))
        row.sidecarTaskID = "conv-1"
        queue.rows.append(row)

        queue.handleFailed(["task_id": "conv-1", "error": "Boom!"])
        XCTAssertEqual(queue.rows.first?.status, .failed)
        XCTAssertEqual(queue.rows.first?.error, "Boom!")
    }

    func test_handleSkipped_records_reason() {
        let queue = ConversionQueueModel()
        var row = JobRow(input: URL(fileURLWithPath: "/tmp/a.note"),
                         output: URL(fileURLWithPath: "/tmp"))
        row.sidecarTaskID = "conv-1"
        queue.rows.append(row)

        queue.handleSkipped(["task_id": "conv-1", "reason": "input_unchanged"])
        XCTAssertEqual(queue.rows.first?.status, .skipped)
        XCTAssertEqual(queue.rows.first?.skipReason, "input_unchanged")
    }

    func test_unknown_task_id_is_silently_ignored() {
        let queue = ConversionQueueModel()
        // Should not crash when the task isn't in our list
        queue.handleFinished(["task_id": "ghost"])
        XCTAssertEqual(queue.rows.count, 0)
    }

    func test_pause_toggles() {
        let queue = ConversionQueueModel()
        XCTAssertFalse(queue.isPaused)
        queue.togglePause()
        XCTAssertTrue(queue.isPaused)
        queue.togglePause()
        XCTAssertFalse(queue.isPaused)
    }
}
