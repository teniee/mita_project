# mobile_app

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Configuration

`ApiService` reads the backend URL from the `API_BASE_URL` Dart define. The
default in `lib/config.dart` is `http://localhost:8000`, which works with the
Docker compose setup. To point the app at a production backend run Flutter with

```bash
flutter build apk --dart-define=API_BASE_URL=https://api.example.com
```

Replace the URL with your deployment.

## In-app purchases

Premium upgrades are verified server-side. `IapService` listens to purchase
updates and sends the purchase receipt to `/api/iap/validate` via
`ApiService.validateReceipt`. Make sure the `API_BASE_URL` variable points to the
running backend when building release artifacts so validation succeeds.
