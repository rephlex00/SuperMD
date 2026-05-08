// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "SuperMD",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(name: "SuperMD", targets: ["SuperMD"]),
    ],
    dependencies: [
        .package(url: "https://github.com/pointfreeco/swift-snapshot-testing", from: "1.17.0"),
    ],
    targets: [
        .executableTarget(
            name: "SuperMD",
            path: "Sources/SuperMD",
            resources: [
                .process("Resources"),
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .testTarget(
            name: "SuperMDTests",
            dependencies: [
                "SuperMD",
                .product(name: "SnapshotTesting", package: "swift-snapshot-testing"),
            ],
            path: "Tests/SuperMDTests",
            resources: [
                .copy("__Snapshots__"),
            ]
        ),
    ]
)

