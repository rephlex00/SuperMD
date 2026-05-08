import SwiftUI

struct JobQueueView: View {
    @EnvironmentObject var app: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Conversion queue")
                .font(.subheadline)
                .padding(.horizontal, 12)
                .padding(.top, 10)
                .padding(.bottom, 6)
                .foregroundStyle(.secondary)

            if app.queue.rows.isEmpty {
                EmptyDropHint().frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(selection: $app.queue.selection) {
                    ForEach(app.queue.rows.reversed()) { row in
                        JobRowView(row: row).tag(row.id)
                    }
                }
                .listStyle(.inset(alternatesRowBackgrounds: true))
            }
        }
    }
}

private struct EmptyDropHint: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "square.and.arrow.down.on.square")
                .font(.system(size: 38))
                .foregroundStyle(.secondary)
            Text("Drop .note, .spd, .pdf, or .png files here")
                .font(.callout).foregroundStyle(.secondary)
            Text("…or enable Cloud sync in Settings")
                .font(.caption).foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

struct JobRowView: View {
    let row: JobRow

    var body: some View {
        HStack(spacing: 10) {
            statusIcon
            VStack(alignment: .leading, spacing: 2) {
                Text(row.input.lastPathComponent).lineLimit(1)
                detailLine
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if row.status == .running, row.totalPages > 0 {
                ProgressView(value: Double(row.currentPage), total: Double(row.totalPages))
                    .frame(width: 90)
            }
        }
        .padding(.vertical, 2)
    }

    @ViewBuilder
    private var detailLine: some View {
        switch row.status {
        case .queued:   Text("Queued")
        case .running:  Text(row.totalPages > 0 ? "Page \(row.currentPage) of \(row.totalPages)" : "Running…")
        case .done:     Text("Done in \(row.durationMs)ms")
        case .skipped:  Text("Skipped — \(row.skipReason ?? "")")
        case .failed:   Text("Failed — \(row.error ?? "unknown")").foregroundStyle(.red)
        }
    }

    private var statusIcon: some View {
        let (symbol, color): (String, Color) = {
            switch row.status {
            case .queued: return ("clock", .secondary)
            case .running: return ("hourglass", .blue)
            case .done: return ("checkmark.circle.fill", .green)
            case .skipped: return ("forward.fill", .gray)
            case .failed: return ("exclamationmark.triangle.fill", .red)
            }
        }()
        return Image(systemName: symbol).foregroundStyle(color)
    }
}
