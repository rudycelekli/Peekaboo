import Foundation
import PeekabooFoundation

@main struct SDKProof {
    static func main() async throws {
        let sleeping = Task { try await Task.sleep(nanoseconds: 10_000_000_000) }
        sleeping.cancel()
        do { try await sleeping.value; fatalError("Swift cancellation swallowed") }
        catch {
            guard error is CancellationError else { fatalError("wrong Swift cancellation") }
            let converted = ErrorStandardizer.standardize(error)
            guard converted.code == .cancelled else { fatalError("Swift task conversion changed") }
            print("CANCELLED_SWIFT_TASK", converted.code.rawValue)
        }
        let environment = ProcessInfo.processInfo.environment
        guard let rawURL = environment["OWNED_CANCEL_URL"], let url = URL(string: rawURL),
              let signalPath = environment["OWNED_REQUEST_STARTED_FILE"]
        else { fatalError("owned loopback request fixture missing") }
        let session = URLSession(configuration: .ephemeral)
        defer { session.invalidateAndCancel() }
        let request = Task { try await session.data(from: url) }
        for _ in 0..<5000 {
            if FileManager.default.fileExists(atPath: signalPath) { break }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        guard FileManager.default.fileExists(atPath: signalPath)
        else { request.cancel(); fatalError("actual URLSession request never reached owned loopback server") }
        request.cancel()
        do { _ = try await request.value; fatalError("URLSession cancellation swallowed") }
        catch {
            let native = error as NSError
            guard native.domain == NSURLErrorDomain, native.code == NSURLErrorCancelled
            else { fatalError("wrong URLSession error") }
            let converted = ErrorStandardizer.standardize(error)
            guard converted.code == .cancelled else { fatalError("URLSession conversion changed") }
            print("CANCELLED_URLSESSION_REQUEST", "actual-owned-request-started", converted.code.rawValue)
        }
        print("PUBLIC_SDK_TRACE_PASS")
    }
}
