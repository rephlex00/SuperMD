import XCTest
@testable import SuperMD

final class LineBufferTests: XCTestCase {
    func test_emits_complete_line_in_one_chunk() {
        var buf = LineBuffer()
        var lines: [String] = []
        buf.append(Data("hello\n".utf8)) { lines.append(String(data: $0, encoding: .utf8)!) }
        XCTAssertEqual(lines, ["hello"])
    }

    func test_holds_partial_line_until_newline_arrives() {
        var buf = LineBuffer()
        var lines: [String] = []
        buf.append(Data("part".utf8)) { lines.append(String(data: $0, encoding: .utf8)!) }
        XCTAssertEqual(lines, [])
        buf.append(Data("ial\n".utf8)) { lines.append(String(data: $0, encoding: .utf8)!) }
        XCTAssertEqual(lines, ["partial"])
    }

    func test_emits_multiple_lines_in_one_chunk() {
        var buf = LineBuffer()
        var lines: [String] = []
        buf.append(Data("a\nb\nc\n".utf8)) { lines.append(String(data: $0, encoding: .utf8)!) }
        XCTAssertEqual(lines, ["a", "b", "c"])
    }

    func test_skips_empty_lines() {
        var buf = LineBuffer()
        var lines: [String] = []
        buf.append(Data("\n\nx\n\n".utf8)) { lines.append(String(data: $0, encoding: .utf8)!) }
        XCTAssertEqual(lines, ["x"])
    }

    func test_handles_split_across_three_chunks() {
        var buf = LineBuffer()
        var lines: [String] = []
        for chunk in ["he", "llo, ", "world\nnext"] {
            buf.append(Data(chunk.utf8)) { lines.append(String(data: $0, encoding: .utf8)!) }
        }
        XCTAssertEqual(lines, ["hello, world"])
    }

    func test_realistic_jsonrpc_framing() {
        var buf = LineBuffer()
        var lines: [String] = []
        let blob = #"{"jsonrpc":"2.0","id":1,"result":{"pong":true}}"#
        // Send byte-by-byte to stress the boundary handling.
        for ch in blob.utf8 {
            buf.append(Data([ch])) { lines.append(String(data: $0, encoding: .utf8)!) }
        }
        XCTAssertEqual(lines, [])  // no newline yet
        buf.append(Data("\n".utf8)) { lines.append(String(data: $0, encoding: .utf8)!) }
        XCTAssertEqual(lines, [blob])
    }
}
