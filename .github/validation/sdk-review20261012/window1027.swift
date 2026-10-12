import Foundation
import PeekabooFoundation

func rejects(_ label: String, _ selector: InteractionTargetSelector, _ expected: InteractionTargetSelector.ValidationError) throws {
    do {
        try selector.validate(policy: .windowCLI())
        throw NSError(domain: "OwnedSDKProof", code: 1, userInfo: [NSLocalizedDescriptionKey: "accepted invalid " + label])
    } catch let error as InteractionTargetSelector.ValidationError {
        guard error == expected else { throw error }
        print("REFUSED", label, String(describing: error))
    }
}
try rejects("pid0", InteractionTargetSelector(processIdentifier: 0), .invalidProcessIdentifier)
try rejects("pid-1", InteractionTargetSelector(processIdentifier: -1), .invalidProcessIdentifier)
try rejects("window0", InteractionTargetSelector(windowID: 0), .invalidWindowID)
try rejects("window-overflow", InteractionTargetSelector(windowID: Int(UInt32.max) + 1), .invalidWindowID)
for id in [1, Int(UInt32.max)] {
    let selector = InteractionTargetSelector(windowID: id)
    try selector.validate(policy: .windowCLI())
    guard try selector.normalizedWindowSelector(policy: .windowCLI()) == .id(id) else { fatalError("valid ID changed") }
    print("ACCEPTED_WINDOW_BOUND", id)
}
for app in ["PID:42", "pid:42", "  PiD:42  "] {
    let selector = InteractionTargetSelector(applicationIdentifier: app, processIdentifier: 42)
    try selector.validate(policy: .windowCLI())
    print("PRESERVED_PID_ALIAS", try selector.normalizedApplicationTarget(policy: .windowCLI()) ?? "nil")
}
print("PUBLIC_SDK_TRACE_PASS")
