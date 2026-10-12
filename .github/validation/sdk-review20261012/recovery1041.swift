import Foundation
import PeekabooFoundation

actor RecoveryEffects {
    private var continuation: CheckedContinuation<Void, Never>?
    private var count = 0
    private var entered = false
    func applyAndSuspend() async {
        self.count += 1
        self.entered = true
        await withCheckedContinuation { self.continuation = $0 }
    }
    func applied() -> Int { self.count }
    func hasEntered() -> Bool { self.entered }
    func finish() { self.continuation?.resume(); self.continuation = nil }
}
struct OwnedRecovery: RecoverableError {
    let effects: RecoveryEffects
    let category: ErrorCategory = .network
    let errorCode = "owned_retry"
    func attemptRecovery() async throws { await self.effects.applyAndSuspend() }
}
@main struct SDKProof {
    static func entered(_ effects: RecoveryEffects) async throws {
        for _ in 0..<1000 {
            if await effects.hasEntered() { return }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        fatalError("owned recovery did not enter")
    }
    static func main() async throws {
        let manager = ErrorRecoveryManager()
        let effects = RecoveryEffects()
        let error = OwnedRecovery(effects: effects)
        let first = Task { try await manager.attemptRecovery(for: error) }
        try await self.entered(effects)
        do { try await manager.attemptRecovery(for: error); fatalError("overlap executed") }
        catch let refused as ErrorRecoveryFailure {
            guard refused.reason == "Recovery already in progress", await effects.applied() == 1
            else { fatalError("incorrect overlap verdict") }
            print("OVERLAP_REJECTED", "effects=1", refused.reason)
        }
        await effects.finish()
        try await first.value
        let later = Task { try await manager.attemptRecovery(for: error) }
        for _ in 0..<1000 {
            if await effects.applied() == 2 { break }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        guard await effects.applied() == 2 else { fatalError("later recovery rejected") }
        await effects.finish()
        try await later.value
        print("LATER_RECOVERY_COMPLETED", "effects=2")
        print("PUBLIC_SDK_TRACE_PASS")
    }
}
