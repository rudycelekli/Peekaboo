import Foundation
import PeekabooFoundation

actor Gate {
    private var continuation: CheckedContinuation<Void, Never>?
    private var entered = false
    func wait() async {
        self.entered = true
        await withCheckedContinuation { self.continuation = $0 }
    }
    func hasEntered() -> Bool { self.entered }
    func release() { self.continuation?.resume(); self.continuation = nil }
}
actor Effects {
    private var count = 0
    func record() { self.count += 1 }
    func value() -> Int { self.count }
}
func entered(_ gate: Gate) async throws {
    for _ in 0..<1000 {
        if await gate.hasEntered() { return }
        try await Task.sleep(nanoseconds: 1_000_000)
    }
    fatalError("owned operation did not enter")
}
@main struct SDKProof {
    static func main() async throws {
        let gate = Gate()
        let inFlight = Task {
            try await performOperation({
                await gate.wait()
                try await Task.sleep(nanoseconds: 10_000_000_000)
                return 1
            }, errorContext: "owned caller cancellation")
        }
        try await entered(gate)
        inFlight.cancel()
        await gate.release()
        do { _ = try await inFlight.value; fatalError("caller cancellation swallowed") }
        catch is CancellationError { print("CALLER_CANCELLATION", "CancellationError") }

        let before = Gate()
        let effects = Effects()
        let precancelled = Task {
            await before.wait()
            return try await performOperation({ await effects.record(); return 1 }, errorContext: "owned precancellation")
        }
        try await entered(before)
        precancelled.cancel()
        await before.release()
        do { _ = try await precancelled.value; fatalError("precancellation swallowed") }
        catch is CancellationError {
            guard await effects.value() == 0 else { fatalError("pre-cancelled effect executed") }
            print("PRE_CANCELLED", "effects=0", "CancellationError")
        }
        print("PUBLIC_SDK_TRACE_PASS")
    }
}
