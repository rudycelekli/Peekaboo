import Foundation
import PeekabooFoundation

actor RecoveryEffects {
    private var count = 0
    func apply() { self.count += 1 }
    func applied() -> Int { self.count }
}
actor Gate {
    private var continuation: CheckedContinuation<Void, Never>?
    private var entered = false
    func wait() async { self.entered = true; await withCheckedContinuation { self.continuation = $0 } }
    func hasEntered() -> Bool { self.entered }
    func finish() { self.continuation?.resume(); self.continuation = nil }
}
struct OwnedRecovery: PeekabooFoundation.RecoverableError {
    let effects: RecoveryEffects
    let isRecoverable: Bool
    let category: ErrorCategory = .network
    let errorCode = "owned_retry"
    func attemptRecovery() async throws { await self.effects.apply() }
}
@main struct SDKProof {
    static func main() async throws {
        let manager = ErrorRecoveryManager()
        let effects = RecoveryEffects()
        do {
            try await manager.attemptRecovery(for: OwnedRecovery(effects: effects, isRecoverable: false))
            fatalError("nonrecoverable dispatched")
        } catch let refused as ErrorRecoveryFailure {
            guard refused.reason == "Error is not recoverable", await effects.applied() == 0
            else { fatalError("nonrecoverable caused effects") }
            print("NONRECOVERABLE_REJECTED", "effects=0")
        }
        let gate = Gate()
        let cancelled = Task {
            await gate.wait()
            try await manager.attemptRecovery(for: OwnedRecovery(effects: effects, isRecoverable: true))
        }
        for _ in 0..<1000 {
            if await gate.hasEntered() { break }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        guard await gate.hasEntered() else { fatalError("owned cancellation gate did not enter") }
        cancelled.cancel()
        await gate.finish()
        do { try await cancelled.value; fatalError("cancelled recovery dispatched") }
        catch is CancellationError {
            guard await effects.applied() == 0 else { fatalError("cancelled dispatch caused effects") }
            print("PRE_CANCELLED_REJECTED", "effects=0")
        }
        try await manager.attemptRecovery(for: OwnedRecovery(effects: effects, isRecoverable: true))
        guard await effects.applied() == 1 else { fatalError("eligible recovery did not execute") }
        print("ELIGIBLE_RECOVERY_COMPLETED", "effects=1")
        print("PUBLIC_SDK_TRACE_PASS")
    }
}
