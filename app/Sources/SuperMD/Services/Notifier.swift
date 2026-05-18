import Foundation
import UserNotifications
import SuperMDObjC

/// Thin wrapper around UNUserNotificationCenter. macOS aborts the process with
/// an NSInternalInconsistencyException when `current()` is called from a
/// bundle the notification daemon doesn't trust (ad-hoc-signed dev builds,
/// processes launched from oddly-pathed binaries). We probe once with an
/// Obj-C try/catch; if the probe blew up we permanently disable ourselves so
/// nothing crashes the app on subsequent conversion-result events.
enum Notifier {
    private static var didRequestAuth = false
    private static var disabled = false
    private static let probeLock = NSLock()
    private static var didProbe = false

    static func notify(title: String, body: String) {
        guard probeCenter() else { return }
        let center = UNUserNotificationCenter.current()
        ensureAuthorized(center) { granted in
            guard granted else { return }
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default
            let req = UNNotificationRequest(
                identifier: UUID().uuidString,
                content: content,
                trigger: nil
            )
            center.add(req, withCompletionHandler: nil)
        }
    }

    /// Try touching the notification center once. If it throws NSException we
    /// log + disable; later calls early-return.
    private static func probeCenter() -> Bool {
        probeLock.lock(); defer { probeLock.unlock() }
        if disabled { return false }
        if didProbe { return true }
        var raised: NSException?
        let exc = SuperMDObjC.tryBlock {
            _ = UNUserNotificationCenter.current()
        }
        raised = exc
        if let raised {
            FileHandle.standardError.write(Data(
                "[Notifier] disabled — UNUserNotificationCenter raised \(raised.name.rawValue): \(raised.reason ?? "")\n".utf8))
            disabled = true
            return false
        }
        didProbe = true
        return true
    }

    private static func ensureAuthorized(_ center: UNUserNotificationCenter,
                                         _ then: @escaping (Bool) -> Void) {
        center.getNotificationSettings { settings in
            switch settings.authorizationStatus {
            case .authorized, .provisional:
                then(true)
            case .notDetermined where !didRequestAuth:
                didRequestAuth = true
                center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
                    then(granted)
                }
            default:
                then(false)
            }
        }
    }
}
