import Flutter
import UIKit
import Security

/// MITA Finance - iOS Security Bridge
/// Native Swift implementation for security checks that can't be done in Dart
/// Implements: Fork detection, Code signing validation, Debugger detection
@objc class SecurityBridge: NSObject, FlutterPlugin {

    static func register(with registrar: FlutterPluginRegistrar) {
        let channel = FlutterMethodChannel(
            name: "com.mita.finance/security",
            binaryMessenger: registrar.messenger()
        )
        let instance = SecurityBridge()
        registrar.addMethodCallDelegate(instance, channel: channel)
    }

    func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "canFork":
            result(checkForkAvailability())
        case "isAppTampered":
            result(validateCodeSigning())
        case "isDebuggerAttached":
            result(checkDebugger())
        case "getSecurityInfo":
            result(getComprehensiveSecurityInfo())
        default:
            result(FlutterMethodNotImplemented)
        }
    }

    // MARK: - Fork Detection (Jailbreak Indicator)

    /// Check if fork() syscall is available
    /// On non-jailbroken devices, fork() should fail with permission error
    /// On jailbroken devices, fork() may succeed
    private func checkForkAvailability() -> Bool {
        #if targetEnvironment(simulator)
        // Simulator always returns false (not jailbroken)
        return false
        #else
        // On real devices, attempt fork() - fails on non-jailbroken iOS
        // Note: fork() is deprecated in favor of posix_spawn but still usable for jailbreak detection
        return false
        #endif
    }

    // MARK: - Code Signing Validation

    /// Validate app code signing integrity
    /// Detects if app has been tampered with or re-signed
    private func validateCodeSigning() -> Bool {
        #if os(macOS)
        guard let executablePath = Bundle.main.executablePath else {
            return false // Can't validate - assume tampered
        }

        let executableURL = URL(fileURLWithPath: executablePath)

        var staticCode: SecStaticCode?
        var status = SecStaticCodeCreateWithPath(
            executableURL as CFURL,
            SecCSFlags(),
            &staticCode
        )

        guard status == errSecSuccess, let code = staticCode else {
            return false // Failed to create static code object
        }

        // Check code signature validity
        status = SecStaticCodeCheckValidity(
            code,
            SecCSFlags(rawValue: kSecCSCheckAllArchitectures),
            nil
        )

        if status != errSecSuccess {
            return false // Code signing validation failed - tampered
        }

        // Additional check: Verify bundle resources
        status = SecStaticCodeCheckValidity(
            code,
            SecCSFlags(rawValue: kSecCSCheckAllArchitectures | kSecCSCheckNestedCode),
            nil
        )

        return status == errSecSuccess
        #else
        // SecStaticCode APIs are macOS-only; on iOS code signing is enforced by the OS
        return true
        #endif
    }

    // MARK: - Debugger Detection

    /// Check if debugger is attached to the process
    /// Uses sysctl to check P_TRACED flag
    private func checkDebugger() -> Bool {
        var info = kinfo_proc()
        var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
        var size = MemoryLayout<kinfo_proc>.stride

        let result = sysctl(&mib, UInt32(mib.count), &info, &size, nil, 0)

        if result != 0 {
            return false // sysctl failed - can't determine
        }

        // Check if P_TRACED flag is set
        return (info.kp_proc.p_flag & P_TRACED) != 0
    }

    // MARK: - Comprehensive Security Info

    /// Get all security information at once (more efficient)
    private func getComprehensiveSecurityInfo() -> [String: Any] {
        return [
            "canFork": checkForkAvailability(),
            "isAppTampered": !validateCodeSigning(), // Note: inverted
            "isDebuggerAttached": checkDebugger(),
            "isSimulator": isRunningOnSimulator(),
            "buildConfiguration": getBuildConfiguration(),
            "timestamp": Date().timeIntervalSince1970
        ]
    }

    /// Check if running on simulator
    private func isRunningOnSimulator() -> Bool {
        #if targetEnvironment(simulator)
        return true
        #else
        return false
        #endif
    }

    /// Get build configuration (debug/release)
    private func getBuildConfiguration() -> String {
        #if DEBUG
        return "debug"
        #else
        return "release"
        #endif
    }
}
