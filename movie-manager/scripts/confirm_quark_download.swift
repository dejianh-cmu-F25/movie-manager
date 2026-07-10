#!/usr/bin/env swift

import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

let appBundleID = "com.quark.clouddrive.desktop"
let appOwnerName = "QuarkCloudDrive"
let dialogTitle = "资源解析"
let waitTimeout: TimeInterval = 20
let closeTimeout: TimeInterval = 5

func fail(_ message: String, code: Int32 = 2) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(code)
}

func matchingWindowBounds() -> CGRect? {
    let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
    guard let windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
        return nil
    }

    for window in windows {
        let owner = window[kCGWindowOwnerName as String] as? String ?? ""
        let name = window[kCGWindowName as String] as? String ?? ""
        guard owner == appOwnerName, name == dialogTitle,
              let boundsValue = window[kCGWindowBounds as String] else {
            continue
        }
        let boundsDictionary = boundsValue as! CFDictionary
        guard let bounds = CGRect(dictionaryRepresentation: boundsDictionary) else {
            continue
        }
        return bounds
    }
    return nil
}

func waitForWindow(until deadline: Date) -> CGRect? {
    while Date() < deadline {
        if let bounds = matchingWindowBounds() {
            return bounds
        }
        Thread.sleep(forTimeInterval: 0.2)
    }
    return nil
}

guard AXIsProcessTrusted() else {
    fail("ChatGPT/Codex does not have macOS Accessibility permission")
}

guard let bounds = waitForWindow(until: Date().addingTimeInterval(waitTimeout)) else {
    fail("Timed out waiting for Quark window: \(dialogTitle)")
}

guard bounds.width >= 650, bounds.width <= 900,
      bounds.height >= 600, bounds.height <= 800 else {
    fail("Unexpected Quark dialog size: \(Int(bounds.width))x\(Int(bounds.height))")
}

NSRunningApplication.runningApplications(withBundleIdentifier: appBundleID).first?
    .activate()
Thread.sleep(forTimeInterval: 0.25)

guard let currentBounds = matchingWindowBounds() else {
    fail("Quark download dialog disappeared before confirmation")
}

// Quark renders this Electron dialog without an accessible AXButton. Click the
// center of the blue "高速下载" button using coordinates relative to the window.
let downloadPoint = CGPoint(
    x: currentBounds.minX + currentBounds.width * 0.8056,
    y: currentBounds.minY + currentBounds.height * 0.8877
)

CGEvent(mouseEventSource: nil, mouseType: .mouseMoved,
        mouseCursorPosition: downloadPoint, mouseButton: .left)?.post(tap: .cghidEventTap)
Thread.sleep(forTimeInterval: 0.15)
CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown,
        mouseCursorPosition: downloadPoint, mouseButton: .left)?.post(tap: .cghidEventTap)
Thread.sleep(forTimeInterval: 0.08)
CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp,
        mouseCursorPosition: downloadPoint, mouseButton: .left)?.post(tap: .cghidEventTap)

let closeDeadline = Date().addingTimeInterval(closeTimeout)
while Date() < closeDeadline {
    if matchingWindowBounds() == nil {
        print("quark_download_confirmed")
        exit(0)
    }
    Thread.sleep(forTimeInterval: 0.2)
}

fail("Quark download dialog remained open after clicking 高速下载")
