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

    // Register MITA security bridge
    let controller = window?.rootViewController as! FlutterViewController
    SecurityBridge.register(with: registrar(forPlugin: "SecurityBridge")!)

    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
