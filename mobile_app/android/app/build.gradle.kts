plugins {
    id("com.android.application")
    id("kotlin-android")
    id("com.google.gms.google-services")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "mita.finance"
    compileSdk = 35
    ndkVersion = "27.0.12077973"

    defaultConfig {
        applicationId = "mita.finance"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }

    // Load keystore properties from file or environment variables
    val keystorePropertiesFile = rootProject.file("key.properties")
    val keystoreProperties = java.util.Properties()

    if (keystorePropertiesFile.exists()) {
        keystoreProperties.load(java.io.FileInputStream(keystorePropertiesFile))
    }

    signingConfigs {
        create("release") {
            // Try to load from file first, then fall back to environment variables
            storeFile = if (keystorePropertiesFile.exists() && keystoreProperties.containsKey("storeFile")) {
                file(keystoreProperties["storeFile"] as String)
            } else {
                System.getenv("KEYSTORE_FILE")?.let { file(it) }
            }

            storePassword = if (keystorePropertiesFile.exists()) {
                keystoreProperties["storePassword"] as String?
            } else {
                System.getenv("KEYSTORE_PASSWORD")
            }

            keyAlias = if (keystorePropertiesFile.exists()) {
                keystoreProperties["keyAlias"] as String?
            } else {
                System.getenv("KEY_ALIAS")
            }

            keyPassword = if (keystorePropertiesFile.exists()) {
                keystoreProperties["keyPassword"] as String?
            } else {
                System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            // Use release signing if credentials are available, otherwise fall back to debug
            signingConfig = if (signingConfigs.getByName("release").storeFile != null) {
                signingConfigs.getByName("release")
            } else {
                println("WARNING: Release keystore not configured. Using debug signing.")
                println("To configure release signing, create key.properties file or set environment variables.")
                signingConfigs.getByName("debug")
            }

            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = "11"
        languageVersion = "2.1"
        apiVersion = "2.1"
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")
}
