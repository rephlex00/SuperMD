import AppKit
import SwiftUI
import XCTest
import SnapshotTesting
@testable import SuperMD

/// Snapshot tests for key SwiftUI views.
///
/// First run: set `isRecording = true` on individual tests (or run with the
/// `RECORD_SNAPSHOTS=1` env var) to generate baselines under
/// `Tests/SuperMDTests/__Snapshots__/`. Commit those PNGs. Subsequent runs
/// compare against them; visual regressions fail the test.
@MainActor
final class ViewSnapshotTests: XCTestCase {

    override func setUp() {
        super.setUp()
        if ProcessInfo.processInfo.environment["RECORD_SNAPSHOTS"] == "1" {
            isRecording = true
        }
    }

    // MARK: - Empty queue (drop hint)

    func test_emptyQueue_lightMode() {
        let app = makeAppModel(rows: [])
        let view = JobQueueView().environmentObject(app)
        assertSnapshot(of: hosted(view, size: CGSize(width: 420, height: 360)),
                       as: .image(precision: 0.98, size: CGSize(width: 420, height: 360)))
    }

    // MARK: - Queue with mixed states

    func test_queueWithMixedStates() {
        let rows: [JobRow] = [
            jobRow(name: "Meeting-2026-05-08.note", status: .running, page: 3, total: 7),
            jobRow(name: "Daily.note", status: .done, durationMs: 4321),
            jobRow(name: "TODO.spd", status: .skipped, skipReason: "input_unchanged"),
            jobRow(name: "Broken.pdf", status: .failed, error: "extractor failed"),
            jobRow(name: "Pending.note", status: .queued),
        ]
        let app = makeAppModel(rows: rows)
        let view = JobQueueView().environmentObject(app)
        assertSnapshot(of: hosted(view, size: CGSize(width: 480, height: 320)),
                       as: .image(precision: 0.98, size: CGSize(width: 480, height: 320)))
    }

    // MARK: - JobRow individual states

    func test_jobRow_running_with_progress() {
        let row = jobRow(name: "Long.note", status: .running, page: 2, total: 8)
        let view = JobRowView(row: row).padding()
        assertSnapshot(of: hosted(view, size: CGSize(width: 420, height: 56)),
                       as: .image(precision: 0.98, size: CGSize(width: 420, height: 56)))
    }

    func test_jobRow_failed_shows_error_in_red() {
        let row = jobRow(name: "Bad.pdf", status: .failed, error: "PyMuPDF: bad header")
        let view = JobRowView(row: row).padding()
        assertSnapshot(of: hosted(view, size: CGSize(width: 420, height: 56)),
                       as: .image(precision: 0.98, size: CGSize(width: 420, height: 56)))
    }

    // MARK: - OTP sheet

    func test_cloudOTPSheet_emptyCode() {
        let app = makeAppModel(rows: [])
        let view = CloudOTPSheet(email: "alice@example.com").environmentObject(app)
        assertSnapshot(of: hosted(view, size: CGSize(width: 380, height: 220)),
                       as: .image(precision: 0.98, size: CGSize(width: 380, height: 220)))
    }

    // MARK: - Helpers

    private func hosted<V: View>(_ view: V, size: CGSize) -> NSView {
        let host = NSHostingView(rootView: view)
        host.frame = NSRect(origin: .zero, size: size)
        return host
    }

    private func jobRow(
        name: String,
        status: JobRow.Status,
        page: Int = 0, total: Int = 0,
        durationMs: Int = 0,
        skipReason: String? = nil,
        error: String? = nil
    ) -> JobRow {
        var r = JobRow(
            input: URL(fileURLWithPath: "/tmp/\(name)"),
            output: URL(fileURLWithPath: "/tmp/out")
        )
        r.status = status
        r.currentPage = page
        r.totalPages = total
        r.durationMs = durationMs
        r.skipReason = skipReason
        r.error = error
        return r
    }

    private func makeAppModel(rows: [JobRow]) -> AppModel {
        let m = AppModel()
        m.queue.rows = rows
        return m
    }
}
