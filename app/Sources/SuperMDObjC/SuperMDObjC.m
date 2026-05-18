#import "SuperMDObjC.h"

NSException * SMDTryBlock(void (^block)(void)) {
    @try {
        block();
        return nil;
    } @catch (NSException *exception) {
        return exception;
    }
}
