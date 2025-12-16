import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // Register Flutter plugins
    GeneratedPluginRegistrant.register(with: self)

    // TEMPORARILY DISABLED: Register MITA security bridge (safe unwrapping)
    // TODO: Add SecurityBridge.swift to Xcode project then uncomment
    // guard let controller = window?.rootViewController as? FlutterViewController,
    //       let registrar = registrar(forPlugin: "SecurityBridge") else {
    //   NSLog("MITA: Failed to register SecurityBridge - FlutterViewController or registrar not available")
    //   return super.application(application, didFinishLaunchingWithOptions: launchOptions)
    // }
    //
    // SecurityBridge.register(with: registrar)
    // NSLog("MITA: SecurityBridge registered successfully")

    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
