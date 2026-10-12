import Foundation
import PeekabooFoundation

@main struct SDKProof {
    static func main() throws {
        let boundary = Double(UInt64.max) / 1_000_000_000
        let values: [(String, TimeInterval, UInt64)] = [
            ("negative", -1, 0), ("zero", 0, 0), ("nan", .nan, 0),
            ("negative-infinity", -.infinity, 0), ("positive-infinity", .infinity, UInt64.max),
            ("upper-bound", boundary, UInt64.max), ("above-upper-bound", boundary.nextUp, UInt64.max),
            ("ordinary", 1.25, 1_250_000_000)
        ]
        for (label, input, expected) in values {
            let actual = input.nanoseconds
            guard actual == expected else { fatalError("wrong conversion for " + label) }
            print(label, actual)
        }
        print("PUBLIC_SDK_TRACE_PASS")
    }
}
