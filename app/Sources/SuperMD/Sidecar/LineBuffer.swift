import Foundation

/// Splits an arbitrary stream of bytes into newline-terminated `Data` chunks.
/// Used by the SidecarManager to demux JSON-RPC frames from a piped stdout
/// where reads can land mid-message.
struct LineBuffer {
    private var buffer = Data()

    mutating func append(_ chunk: Data, _ onLine: (Data) -> Void) {
        buffer.append(chunk)
        while let nl = buffer.firstIndex(of: 0x0A) {
            let line = buffer.subdata(in: buffer.startIndex..<nl)
            buffer.removeSubrange(buffer.startIndex...nl)
            if !line.isEmpty { onLine(line) }
        }
    }
}
