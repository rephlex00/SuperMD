import Foundation
import UserNotifications

/// Thin wrapper around UNUserNotificationCenter. First call lazily requests
/// authorization. Silent on failure — notifications are nice-to-have, not
/// critical, so we don't surface auth errors to the user.
enum Notifier {
    private static var didRequestAuth = false

    static func notify(title: String, body: String) {
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
