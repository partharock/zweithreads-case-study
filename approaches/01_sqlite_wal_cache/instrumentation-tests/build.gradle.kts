plugins {
    id("com.android.library")
}

android {
    namespace = "com.autotech.aaos.contactscache.integration"
    compileSdk = 34

    defaultConfig {
        minSdk = 31
        targetSdk = 34
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        consumerProguardFiles("consumer-rules.pro")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        getByName("main") {
            java.srcDirs("../src/main/java")
            manifest.srcFile("src/main/AndroidManifest.xml")
        }
        getByName("androidTest") {
            java.srcDirs("src/androidTest/java")
        }
    }

    testOptions {
        animationsDisabled = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:rules:1.6.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:core:1.6.1")
    androidTestImplementation("androidx.annotation:annotation:1.9.1")
}
