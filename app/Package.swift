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
            dependencies: ["SuperMD"],
            path: "Tests/SuperMDTests"
        ),
    ]
)
