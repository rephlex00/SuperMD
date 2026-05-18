#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

/// Run `block` inside @try / @catch and return any NSException it raised.
/// Used to defensively call AppKit / Foundation APIs that throw ObjC
/// exceptions Swift can't otherwise catch (e.g. UNUserNotificationCenter
/// from a non-bundle-trusted process).
__attribute__((swift_name("tryBlock(_:)")))
NSException * _Nullable SMDTryBlock(void (^_Nonnull block)(void));

NS_ASSUME_NONNULL_END
